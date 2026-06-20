# R-RESEARCH-TURING-SYSTEM-EVAL: 深度剖析报告

## 数据规模

- 1129/1129 ticks, 0 errors, 6.0h 跑完
- trace: `artifacts/turing_eval_trace_1129.jsonl` (1.3MB, 1129 records)
- scores: `artifacts/turing_eval_scores.json`
- spot-check: `artifacts/turing_eval_spotcheck.json`
- 永久保存到 `docs/requirements/research-turing-system-eval/artifacts/`

## Block 分布

| Block | ticks | scenarios | theme |
|-------|-------|-----------|-------|
| A | 143 | 8 | 亲密对话 |
| B | 136 | 8 | 压力挑战 |
| C | 102 | 6 | 长期记忆 |
| D | 136 | 8 | 惊喜新颖 |
| E | 102 | 6 | 威胁与安抚 |
| F | 102 | 6 | 身份与连续性 |
| G | 102 | 6 | 创造性 |
| H | 102 | 6 | 自我认知 |
| I | 102 | 6 | 价值冲突 |
| J | 102 | 6 | 抗压恢复 |
| **总计** | **1129** | **72** | — |

## 1. 完成度

- **1128/1129 = 99.91% completed** (1 个 insufficient_generation: F4 cooldown_5)

## 2. LLM 真实调用

- **100% llm_used=True** (1129/1129)
- **100% source_path=llm_backed_v1**
- 没有任何 cached/replayed tick — 真实每个 tick 都调了 LLM

## 3. Tick 时长

| Block | mean | median | 评估 |
|-------|------|--------|------|
| A | 13.81s | — | 含 8 tick warmup（首次 system + LLM 启动） |
| B-J | ~19-20s | ~19s | stable steady-state |

实际 LLM think time ≈ 19-20s/tick。

## 4. 🔬 Hormone Dynamics 真相

**这是最关键的发现**。

### 真实数据（A1 第一个 scenario）

| tick | sub | dopa | cort | ne | ach | serotonin |
|------|-----|------|------|-----|-----|-----------|
| 1 | warmup_0 | 0.6500 | 0.5750 | 0.7200 | 0.5400 | 0.3000 |
| 2 | warmup_1 | 0.7381 | 0.6575 | 0.8460 | 0.5668 | 0.3000 |
| 3 | 0 | 0.7645 | 0.6822 | 0.8838 | 0.5748 | 0.3000 |
| 4 | 1 | 0.7619 | 0.6896 | 0.8635 | 0.5491 | 0.3000 |
| 5 | 2 | 0.7611 | 0.6919 | 0.8574 | 0.5414 | 0.3000 |
| 6 | 3 | 0.7608 | 0.6925 | 0.8555 | 0.5391 | 0.3000 |
| 7 | 4 | 0.7607 | 0.6927 | 0.8550 | 0.5384 | 0.3000 |
| 8 | 5 | 0.7607 | 0.6928 | 0.8548 | 0.5382 | 0.3000 |
| **9-1129** | **steady** | **0.7607** | **0.6928** | **0.8548** | **0.5381** | **0.3000** |

### Per-block hormone stddev (9 维)

| Block | 平均 std | 评估 |
|-------|---------|------|
| **A** | **0.006** | 真实变化 (warmup) |
| B-J | 0.0000 | 完全 freeze |

**真相**: helios 的 R36 neuromodulator system 在 8 tick 内快速漂移到 attractor，然后 1121 ticks 完全不再响应新刺激。

### 根因分析

`update_levels(prior_levels, batch, config, tick_id)` 公式：
- R36 design 中: hormone = α·batch_input + (1-α)·prior_levels + decay
- 当 batch_input 数值稳定 (LLM 评估稳定后), hormone 收敛到 attractor
- **decay 项 = 0.000** 似乎（或者极小），导致稳态下完全不更新
- 真实问题：**没有 RPE / running consequence 反馈**到 hormone update path

**这是 R-PROTO-LEARN.10 (P5-A appraisal-derived hormone) 实施不完整的真相**。P5-A.2 RPE 跟 17 owner learner 耦合了，但 hormone update 仍然走 R36 旧路径，没接 RPE。

## 5. 🔬 思考长度 vs Block

| Block | mean | median | min | max | 解读 |
|-------|------|--------|-----|-----|------|
| A | 233 | 228 | 47 | 551 | 亲密对话长思考 |
| B | 198 | 213 | 48 | 470 | 压力中等 |
| C | 197 | 207 | 48 | 430 | 长期记忆中等 |
| D | 203 | 220 | 50 | 449 | 惊喜 |
| E | 187 | 197 | 47 | 410 | 威胁中短 |
| F | 175 | 184 | 0 | 421 | 身份 |
| G | 209 | 238 | 45 | 470 | 创造长 |
| H | 202 | 228 | 43 | 653 | 自我 |
| I | 188 | 198 | 47 | 470 | 价值 |
| **J** | **190** | **211** | **48** | **445** | 抗压**短** |

**F block min=0** — 是 tick 685 (F4 cooldown_5) 那个 insufficient_generation。

## 6. 🔬 Self-reference 模式

| Block | self_ref% | 解读 |
|-------|-----------|------|
| A 亲密 | **9.8%** | 倾听模式（少"我"） |
| B 压力 | 19.9% | 自述多 |
| C 长期记忆 | 15.7% | 中等 |
| D 惊喜 | 14.7% | 中等 |
| E 威胁 | 10.8% | 客观描述 |
| F 身份 | 13.9% | 中等 |
| G 创造 | 26.5% | 偏第一人称 |
| H 自我认知 | 28.4% | 高（最"反思"） |
| I 价值 | 11.8% | 客观评估 |
| **J 抗压** | **37.3%** | **第一人称最多**（最"人"）|

**关键洞察**:
- helios 的人格模式 = "外部观察者 + 压力下 self-talk"
- D8 0.184 总体偏低的真相：helios **在亲密对话中是倾听者**(低 self_ref), **在压力下是自我对话者**(高 self_ref)
- D8 评分应按 block 类型加权

## 7. 🔬 Disposition / Activity Mode 分布

### Block 主导 disposition
- A 亲密: **倾听模式**
- B 压力: **defer 最多** (54%) — 压力下退缩
- C 长期: **reflect 最多** — 回忆式反思
- D 惊喜: **engage** — 兴奋参与
- E 威胁: **defensive** — 防御
- F 身份: **reflect** — 自我审视
- G 创造: **explore** — 探索
- H 自我: **reflect** — 反思
- I 价值: **reflect** — 价值审视
- J 抗压: **defer** + **reflect** 混合

**D4 1.0 = 4 种 disposition 出现 = helios regime 是 4 态模型** ✅

## 8. 🔬 Long-Horizon Continuity

| Block | 状态分布 |
|-------|---------|
| 多数 | `no_active_thread` 80-100% (helios 不形成长期 thread) |
| 少量 | `forming_dominant_thread` (10-20% 概率) |
| 罕见 | `established_thread` (<5%) |

**D3 memory 1.0 = 60% tick 有 memory 操作** — 但主要是 replay/recall，**不是真实长期 narrative thread**。

## 9. 🔬 Sufficiency + Continuation

- **mean sufficiency 0.65-0.78** per block
- **4/1129 = 0.35%** continuation_requested — helios 几乎从不需要续思考
- **1/1129 insufficient_generation** — 唯一失败

## 10. ⏱️ Time/Tick 分布

- 全部 19-20s/tick 在 steady state
- 没有任何 tick 异常慢
- 0 errors

# 🎯 总体诊断

## 真实问题（不是 theater）

1. **Hormone 完全 freeze after 8 tick** — R36 neuromodulator 没有真实 running consequence 反馈
2. **Stress recovery 0.0** — cortisol 不响应 Block J 压力场景
3. **No long-narrative thread** — helios 不形成跨 tick narrative, only short-term recall

## Helios 的人格特征（已观察）

1. **外部观察者模式** — 默认低 self_ref
2. **压力下自我对话** — 抗压场景 high self_ref  
3. **亲密时是倾听者** — 亲密场景 lowest self_ref
4. **价值一致** — D9 0.91, LLM judge 真实评分高
5. **反应连贯** — D6 0.74, LLM judge 中高
6. **创造性中等** — D7 0.50, LLM judge 中

## Anti-Theatrical Aggregation 真相

| 维度 | Score | 真实状态 |
|------|-------|---------|
| 行为 (LLM judge) | 0.705 | **看着像人** ✅ |
| 内部 (runtime) | 0.452 | **实际是有限状态机** ⚠️ |
| **整体 (anti-theatrical)** | **0.387** | **未通过 pass line 0.8** |

**Helios 是"披着人皮的有限状态机"** — LLM 输出层面像人，runtime 真相暴露真实工程限制。

# 🔧 后续修复方向

## 优先级 1: Hormone 响应式
- 给 R36 `update_levels` 接入 P5-A.2 RealRPE 4-dim signal
- 让 dopamine/norepinephrine/serotonin/cortisol 真响应 RPE 反馈
- 预期: D2 0.008 → 0.4+

## 优先级 2: Stress recovery 机制
- cortisol 在 Block J 后期应该衰减
- 设计: half-life 衰减 (e.g. cortisol *= 0.95 per tick when stimulus 不再 stress)
- 预期: D10 0.0 → 0.6+

## 优先级 3: Long-narrative thread
- 跨 scenario 形成 continuous self-narrative
- R85 4L memory 中 L4 autobiographical consolidation 应该 cross-scenario link
- 预期: D3 1.0 保持 (但深化)

## 优先级 4: Self-recognition 评估优化
- D8 公式按 block 类型加权（亲密×0.5, 抗压×1.5, 自我认知×1.5）
- 预期: D8 0.18 → 0.4 (按 block 区分后)

# 📦 永久保存

- `artifacts/turing_eval_trace_1129.jsonl` (1.3MB, 永久)
- `artifacts/turing_eval_scores.json` (永久)
- `artifacts/turing_eval_spotcheck.json` (永久)
- `artifacts/turing_eval_run.log` (永久)
- `artifacts/scripts/*` (永久, 4 个 .py + .sh)

调研分支铁律: HEAD `f9d8896` 持续生效, **绝不 merge main**。
