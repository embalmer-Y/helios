# Task: P5-feel — owner 05 feeling 真学习算法

> 配套 requirement.md / design.md
> 任务模式：调研分支直接 ship 最终目标（**5 项 1 commit**，不切分）
> 验证：整库测试 + 真 LLM smoke + 行为验收

## 1. 任务总览

| # | 任务 | 时间估计 | 依赖 |
|---|---|---|---|
| 1 | 写 `feeling/learning_path.py` 主体（5 项算法） | 60 min | — |
| 2 | owner 05 集成（P5FeelLearningPath 注入）| 30 min | T1 |
| 3 | 写 `tests/test_r_proto_learn_7_p5_feel.py`（30+ 测试）| 45 min | T1+T2 |
| 4 | 跑整库 `pytest tests/ -q --ignore=scratch_r79b` | 5 min | T1-T3 |
| 5 | 真 LLM smoke 改造（8 条原 + 5-7 条新）| 30 min | T1-T3 |
| 6 | 跑真 LLM smoke 验证 | 5 min | T5 |
| 7 | 暴露 bug 修（同 commit）| 30 min | T6 |
| 8 | commit + push | 5 min | T1-T7 |

**总计**：~3.5 小时（不切分，连续 1 个 commit）

## 2. 任务详情

### T1. 写 `feeling/learning_path.py` 主体

**位置**：`src/helios_v2/feeling/learning_path.py`（新文件）

**内容**：
- `Regime` (enum, 3 态)
- `P5FeelLearningConfig` (frozen dataclass: lr, threshold, clip, min_stable_ticks, precision_floor/ceiling, flexibility_threshold, frozen_ticks_post_commit)
- `P5FeelLearningPath` (class)
  - `__init__(self, config, initial_W, initial_bias)` (initial_W = R36 hardcoded 7×9, initial_bias = R36 hardcoded 7 维)
  - `update(hormone, llm_appraisal, prior_feeling, novelty, dopamine, acetylcholine, tick_id) -> (W_new, bias_new, regime)`
  - 5 项算法 private methods: `_explore_residual`, `_should_commit`, `_dopamine_precision`, `_ach_flexibility`, `_determine_regime`
  - 3 态 W 更新公式（在 update 内部）
  - `regime()`, `weights_snapshot()`, `commit_if_stable()` 公开方法
  - `__post_init__` 验证 config 合法
  - 所有数值 clip + 边界检查

**细节**：
- 使用 `numpy` 或纯 Python（**优先纯 Python**，不引新依赖；如必须 numpy 看情况）
- 7×9 = 63 weight + 7 bias = 70 个 float 参数学习
- 残差 history 用 `collections.deque(maxlen=20)`

### T2. owner 05 集成

**位置**：`src/helios_v2/feeling/engine.py`（轻微改动）

**内容**：
- `InteroceptiveFeelingConfig` 加 `p5_feel_path: P5FeelLearningPath | None = None`（opt-in，默认 None）
- `InteroceptiveFeelingState` 加 `weights: tuple[tuple[float, ...], ...]` + `bias: tuple[float, ...]`（默认 = R36/R43 hardcoded）
- `update_state(...)` 在 `update_feeling_state` 公式后调 `p5_feel_path.update(...)` 拿到新 W/bias → 写入新 state
- **边界保持**：owner 05 不直接调 LLM；LLM appraisal 通过 Protocol 注入
- **backward compat**：不传 `p5_feel_path` 时行为不变（R36/R43 hardcoded）

**Protocol 注入**：
- `LlmAppraisalSource`（已存在，R-PROTO-LEARN.2）— 直接复用
- `NeuromodulatorStateSource`（已存在，R-PROTO-LEARN.1）— 直接复用
- 注入方式与 R-PROTO-LEARN.1/.2 一致（Protocol runtime_checkable + 注入式 source）

### T3. 写测试

**位置**：`tests/test_r_proto_learn_7_p5_feel.py`（新文件）

**测试覆盖（30+）**：
- 探索残差计算（5）：
  - 零残差 → 零信号
  - 正向残差 → 正向 W 更新
  - LLM appraisal is None → 跳过
  - 7 维残差 > 0.05 维数 > 3 → 不算探索信号
  - 残差 clip
- 固化判定（5）：
  - 滑窗不足 → 不 commit
  - 滑窗稳定 → commit
  - 残差波动 → 不 commit
  - commit 冻结 → 后续 N tick 不再 commit
  - commit 阈值边界
- DA precision（5）：
  - DA=0.5 + 零残差 → precision 中等
  - DA=1.0 + 零残差 → precision 高
  - DA=0.0 → precision floor
  - 大残差 → precision 衰减
  - precision clip
- ACh flexibility（5）：
  - ACh < threshold → flexibility floor
  - ACh > threshold + novelty 高 → flexibility 高
  - ACh > threshold + novelty 低 → flexibility 中
  - flexibility clip
  - 0.4 threshold 边界
- 三态切换（5）：
  - 早期 → EXPLORATORY
  - 收敛 → HABITUAL
  - ACh + novelty 高 → EXPLORATORY
  - 默认 → MODEL_BASED
  - 切换稳定性（hysteresis）
- W 更新 clip / 数值稳定（5）：
  - 大学习率不爆
  - 大残差不爆
  - 大 hormone 不爆
  - 连续 100 tick 不发散
  - 数值 clip 边界

### T4. 跑整库

```bash
cd /root/project/helios/helios_v2 && set -a && . /root/project/helios/.env && set +a && \
.venv/bin/python3 -m pytest tests/ -q --ignore=scratch_r79b \
  --ignore=tests/r88_drift_evaluator --ignore=tests/r89_turing_harness \
  --ignore=tests/r90_memory_fidelity_probe --ignore=tests/test_performance_benchmark.py \
  --ignore=tests/test_long_term_stability_prerequisites.py \
  --ignore=tests/test_assemble_runtime_wall_clock_profile.py
```

**预期**：
- 整库 baseline 1253 passed + 3 skipped + 0 failed
- 加 T3 后：~1283 passed + 3 skipped + 0 failed（+30 新测试）

**失败处理**：
- 测试失败 → 修算法 / 修集成 / 修测试
- **不切分**（按小黑拍板）
- 反复修直到 0 失败

### T5. 真 LLM smoke 改造

**位置**：`scripts/r_proto_learn_p5_feel_smoke.py`（新文件）

**内容**：
- 沿用 `scripts/r_proto_learn_real_llm_smoke.py` 8 条 ZH 情绪对话
- 增 5-7 条 cover 慢路径：
  - "连续 calm"（低 ACh / 高 serotonin → 固化）
  - "突然 changing"（高 ACh / novelty 高 → 探索）
  - "激素稳定但情绪转"（DA precision 触发）
  - "重复同情绪"（ACh 衰减）
  - "持续 cortisol 高"（学习 stress 习惯）
- 每个对话跑 10-30 tick
- 观察：
  - 7 维 feeling 是否与 LLM appraisal 方向一致
  - W 矩阵 70 个参数在 N tick 后真变化
  - DA precision 真作用
  - ACh flexibility 真触发
  - 三态切换可观察

### T6. 跑真 LLM smoke 验证

```bash
cd /root/project/helios/helios_v2 && set -a && . /root/project/helios/.env && set +a && \
.venv/bin/python3 scripts/r_proto_learn_p5_feel_smoke.py
```

**预期**：
- 8-15 条对话全部跑通
- LLM call 成功率 ≥ 80%
- W 矩阵有非平凡变化
- 7 维 feeling 方向正确

**失败处理**：
- 算法 bug → 修 P5FeelLearningPath
- LLM 输出异常 → 改 prompt 或不归责 P5-feel
- 集成 bug → 修 owner 05 engine
- **不切分**（按小黑拍板）

### T7. 暴露 bug 修

**前提**：T4 或 T6 暴露 bug

**动作**：
- 同一个 commit 内修
- 不切分
- 修后重跑 T4 + T6

**例外**：如果**整套方案根本性不可行**（如 LLM 评估太不稳定 / 三态切换逻辑错误 / W 矩阵学习发散）→ 报告小黑 → 决定是返工还是放弃

### T8. commit + push

**commit message 格式**（沿用 R-PROTO-LEARN 风格）：
```
feat(R-PROTO-LEARN.7): P5 feel 真学习 — owner 05 channel→dim 真自我学习 (IMAC 5 算法)

学术 ground truth 一次性 ship（按主人 2026-06-16 19:50 拍板"直接全套最终目标"）：
- 探索阶段 (aINS-equivalent): R-PROTO-LEARN.2 LLM appraisal 作 ground truth
- 固化阶段 (gINS-equivalent): 连续 N tick mapping 不变 → 写入 config
- 精度信号 (DA): R81 precision signal 范式，dopamine 调 confidence
- 灵活性信号 (ACh): novelty * ACh → flexibility，3 态切换
- 三态切换 (IMAC): aINS / dINS / gINS = R88 漂移收敛触发

新文件:
- src/helios_v2/feeling/learning_path.py
- scripts/r_proto_learn_p5_feel_smoke.py
- tests/test_r_proto_learn_7_p5_feel.py
- docs/requirements/research-p5-feel/{requirement,design,task,research_notes}.md

集成:
- feeling/engine.py: InteroceptiveFeelingConfig + State 加 W/bias 字段 (opt-in)
- Protocol 注入: LlmAppraisalSource (R-PROTO-LEARN.2) + NeuromodulatorStateSource (R-PROTO-LEARN.1)

测试: 整库 +30 测试 (1253 → 1283 passed, 0 failed)
真 LLM smoke: 8-15 条 ZH 情绪对话, 5 项算法全部 ship

学术依据:
- Fermin, Yamawaki, Friston (2021) IMAC 模型 (arXiv 2112.12290)
- Reddan, Chang, Kragel, Wager (2018) embodied emotion (arXiv 2411.08973)
- Hinrichs et al. (2025) hyperscanning (arXiv 2506.08599)
- Seth 2013 / Barrett 2017 / Friston 2010 (经典)
```

**push**：
```bash
cd /root/project/helios/helios_v2 && git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```

## 3. 任务依赖图

```
T1 ─► T2 ─► T3 ─► T4 ─┬─► T7 ─► T8
                       │
                       └─► T5 ─► T6 ─► T7
```

T7 可能在 T4 或 T6 触发。

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 5 项一起 ship 太大 | 单元测试 + 集成测试 充分覆盖 |
| 真实 LLM 暴露 bug | T7 同 commit 修 |
| 三态切换不稳 | 加 hysteresis |
| W 矩阵发散 | clip + 限制学习率 |
| 集成破坏 owner 05 边界 | Protocol 注入 + opt-in default |
| 整库测试暴露未预见的耦合 | 修 + 重跑 |

## 5. 验收检查表

- [ ] T1: learning_path.py 完成
- [ ] T2: owner 05 集成完成
- [ ] T3: 30+ 测试写完
- [ ] T4: 整库测试 0 失败
- [ ] T5: smoke 脚本完成
- [ ] T6: smoke 跑通（≥ 80% LLM 成功）
- [ ] T7: 所有暴露 bug 修完
- [ ] T8: commit + push 成功

**全部 ✅ = 切片 ship 成功**
