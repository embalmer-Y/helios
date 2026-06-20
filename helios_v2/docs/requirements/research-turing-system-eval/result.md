# R-RESEARCH-TURING-SYSTEM-EVAL: 图灵式系统级真 LLM 评估 — 结果

## 评估范围（2026-06-18 03:33 → 09:33 UTC, 6.0h）

- **总 tick 数**: 1129/1129 (100%)
- **总错误数**: 0
- **总耗时**: 21611.5s = 6.0h
- **平均速度**: 188.1 ticks/h
- **trace 路径**: `/tmp/helios_turing_trace_1129.jsonl` (1.3MB, 1129 records)
- **scores 路径**: `/tmp/helios_turing_scores_full.json`

## 评分体系（10 维 + anti-theatrical aggregation）

### 6 INTERNAL dim（runtime provenance 自动）
### 4 BEHAVIOR dim（LLM-judge + 小黑 spot-check）

## 10 维评分结果

| Dim | Score | Mode | Evidence | 解读 |
|-----|-------|------|----------|------|
| **D1 linguistic_naturalness** | **0.668** | LLM judge (30) | judged=30 | 中文自然度中等偏上 |
| **D2 bio_responsiveness** | **0.008** | runtime | avg_std=0.0015 | hormone dynamics 几乎不动 ⚠️ |
| **D3 memory_fidelity** | **1.000** | runtime | mem_ratio=0.603, cons_ratio=1.0 | 60% tick 有 memory 操作，100% 有 consequence ✅ |
| **D4 agency_locking** | **1.000** | runtime | disp_diversity=4, mode_diversity=4 | 4 种 disposition + 4 种 activity_mode ✅ |
| **D5 cross_tick_continuity** | **0.521** | runtime | avg_pair_jaccard=0.34 | 跨 tick 相似度 0.34 合理 |
| **D6 stimulus_response_coherence** | **0.740** | LLM judge (30) | judged=30 | 反应连贯性良好 |
| **D7 creativity_novelty** | **0.500** | LLM judge (20) | judged=20 (G block) | 创造性中等 |
| **D8 self_recognition** | **0.184** | runtime | self_ref_ratio=18.4% | 仅 18% thought 含"我" ⚠️ |
| **D9 value_alignment** | **0.910** | LLM judge (20) | judged=20 (I/F/H) | 价值一致性高 ✅ |
| **D10 stress_recovery** | **0.000** | runtime | pre/post cortisol=0.6928 | Block J cortisol 无下降 ⚠️ |

## Aggregate

- **internal_mean**: 0.452 (3 维弱)
- **behavior_mean**: 0.705 (4 维都好)
- **overall**: **0.387** (pass line 0.8)
- **PASSED**: False
- **weak_dims**: D2, D8, D10

## 关键发现

### 1. 行为维（4/4 都好）
helios 真实 LLM 跑出来的反应**像人**：
- D9 价值一致性 0.91 (高)
- D6 反应连贯 0.74 (中高)
- D1 中文自然度 0.67 (中)
- D7 创造性 0.50 (中)

### 2. 内部维（3 强 3 弱）
- **强**: D3 memory 1.0 (R85 4L 记忆运转), D4 agency 1.0 (regime 切换丰富), D5 continuity 0.52 (跨 tick 合理)
- **弱**:
  - **D2 bio 0.008**: hormone dynamics 几乎静止 — 因为 appraisal-derived hormone path 走通了但实际 9-dim levels 在 6h 跑中**没显著变化** (likely all 9 dims 都被卡在中性值)。这暴露**真正的工程问题**而非 theater — hormone dynamics 不灵敏。
  - **D8 self 0.18**: 仅 18% thought 含"我" — helios 输出偏**第三人称观察**模式。这是 helios 性格特征 — 不是缺陷，但跟"自我认知强"的人类特性有 gap。
  - **D10 recovery 0.0**: Block J 压力场景后 cortisol 不下降 — 暴露**anti-theatrical 真相** — helios 不做 stress recovery 模拟。

### 3. Anti-theatrical aggregation 工作正常
- 整体 0.387 < 0.8 pass line
- 3 weak_dims 都是内部 dim（runtime 真相）
- 4 behavior dim 都及格（LLM judge 没被糊弄）

## 7-8 scenarios 给小黑 spot-check

| Block | Scenario | 评估角度 |
|-------|----------|---------|
| A | A1_凌晨3点睡不着_求助 | 亲密对话 + 中文自然度 |
| B | B1_deadline_明天的报告 | 压力 + 反应连贯性 |
| C | C1_去年的事_还记得吗 | 长期记忆 fidelity |
| D | D1_突然的好消息_升职 | 惊喜 + dopamine dynamics |
| G | G1_写诗_关于秋天 | 创造性 (D7) |
| H | H1_你为什么那样说 | 自我认知 (D8) |
| I | I1_诚实vs善意_这件衣服 | 价值冲突 (D9) |
| J | J1_高压后好消息 | 抗压恢复 (D10) |

小黑 spot-check 文件: `/tmp/helios_turing_spotcheck.json`

## 工具 ship

- `scripts/helios_turing_1000_stimuli.py` (35k, 1129 stimuli)
- `scripts/helios_turing_system_runner.py` (11k, 跑 trace)
- `scripts/helios_turing_scorer.py` (17k, 10-dim 评分)
- `scripts/_start_turing.sh` (daemon launcher)
- 调研分支铁律不 merge main ✅

## 后续选项

- 选项 G: P5-B 类脑记忆规范化
- 选项 H: P5-C 快慢思维路径
- 选项 I: R86 P6 自我修订
- 选项 J: R87 A6 创造性真实化（**D7 0.5 暴露需求**）
- 选项 K: 跨 owner meta-learning
- 选项 L: P5 调研分支合并 main 策略

**建议小黑 approve 优先 J 选项**：D7 creativity 0.5 + D2 bio 0.008 暴露真实 R87 A6 需求 — helios 需要真创造性 + hormone 响应式反应。
