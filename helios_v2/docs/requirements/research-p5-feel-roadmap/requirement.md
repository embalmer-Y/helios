# R-PROTO-LEARN 后续路线图 — 深度调研

## 调研目的

P5-feel 真学习（owner 05）已经 10 个切片 ship（R-PROTO-LEARN.1-10），剩下的
P5 缺口（17 owner × 54 mandatory_learned_parameter category 中**还有 46 个
未实现**）需要系统性的后续开发规划。本文件是对后续路线的**深度调研**
（基于 Kotseruba 2018 / De Lange 2021 / Bhatt 2019 / Parisi 2019 /
Einhauser 2018 五篇核心论文 + helios 17 owner 矩阵的真实缺口地图）。

## 当前 P5 缺口地图（17 owner × 54 category）

| Owner | LPC 总数 | 已实现 | 未实现 | 占比 |
|---|---|---|---|---|
| 04 neuromodulation | 5 | 5 (R81 + R10) | 0 | 0% |
| 05 feeling | 3 | 3 (R-PROTO-LEARN.7/9) | 0 | 0% |
| 06 memory | 3 | 0 | **3** | 100% |
| 07 workspace | 3 | 0 | **3** | 100% |
| 08 consciousness | 3 | 0 | **3** | 100% |
| 09 thought_gating | 3 | 0 | **3** | 100% |
| 10 directed_retrieval | 3 | 0 | **3** | 100% |
| 11 internal_thought | 3 | 0 | **3** | 100% |
| 12 action_externalization | 3 | 0 | **3** | 100% |
| 13 planner_bridge | 3 | 0 | **3** | 100% |
| 14 identity_governance | 4 | 0 | **4** | 100% |
| 15 experience_writeback | 3 | 0 | **3** | 100% |
| 16a outward_expression | 3 | 0 | **3** | 100% |
| 16b outward_expression_externalization | 3 | 0 | **3** | 100% |
| 17 evaluation | 3 | 0 | **3** | 100% |
| 18 autonomy | 3 | 0 | **3** | 100% |
| prompt_contract (07/16a) | 3 | 0 | **3** | 100% |
| **合计** | **54** | **8 (15%)** | **46 (85%)** | -- |

**P5 缺口 = 46 个 mandatory_learned_parameter category 完全未实现**。

## 学术调研 — 5 篇核心论文

### 1. Kotseruba & Tsotsos 2018 "40 years of cognitive architectures"

**DOI**: 10.1007/s10462-018-9646-y (cited 515)
**核心论点**:
- 84 个 cognitive architecture 综述，49 个仍在 active development
- **3 大 metacognition 机制**：
  1. **Self-observation** (内省观察) — AIS/COGNET/Soar/CLARION
  2. **Self-analysis** (内省分析)
  3. **Self-regulation** (内省调节)
- "metacognition" 是从 R86 开始的 P6 主题
- **架构选择分类**：symbolic / emergent / hybrid

**对 helios 启示**:
- helios 是 hybrid（symbolic owner + emergent LLM）
- P6 self-regulation = helios R86+ 主题
- helios 17 owner × 3-5 category = 一份完整的 metacognition 体系

### 2. De Lange et al. 2021 "A continual learning survey: defying forgetting"

**DOI**: 10.1109/tpami.2021.3057446 (cited 1590)
**核心论点**:
- 3 大 continual learning 场景
- **replay-based 唯一在所有场景下都 work**；EWC/SI 等 regularization
  方法在 "task identity needs to be inferred" 时**完全失败**
- 没有"一种方法统治所有场景"

**对 helios 启示**:
- helios 的 4 层 L2-L5 memory store (R85) 跟 **replay-based** 范式对位
- R-PROTO-LEARN.3 (Layer 3 predictive coding) + R-PROTO-LEARN.4 (Layer 4
  pattern completion) = **replay + prediction** 双重保险
- owner 06 memory 的 `replay_priority_policy` 跟 Parisi 2019 6 大神经
  机制中的 "memory replay" 直接对位

### 3. Bhatt et al. 2019 "Is plasticity of synapses the mechanism of long-term memory storage?"

**DOI**: 10.1038/s41539-019-0048-y (cited 379)
**核心论点**:
- 记忆存储**不一定**在突触
- **reconsolidation 是学习窗口**（不只是巩固）：reconsolidation blockade
  能消除突触增长，但**记忆仍存在**（说明记忆不在突触）
- **DNA methylation 是 engram 的最可能机制**（比 LTP 更稳定）

**对 helios 启示**:
- R85 的 4 层 L2-L5 store 跟 LTP→DNA methylation 双时间尺度对位
- R86 4 层 reconsolidation 路线跟 "reconsolidation = learning window"
  学术依据吻合
- owner 15 experience_writeback 的 `consolidation_priority_policy` 跟
  DNA methylation engram 机制对位（**长期 consolidation = 跨 tick 持久**）

### 4. Parisi et al. 2019 "Continual lifelong learning with neural networks: A review"

**DOI**: 10.1016/j.neunet.2019.01.012 (cited 3001, arXiv 1802.07569)
**核心论点 — 6 大神经机制**:
1. **Structural plasticity** (神经发生 — adult neurogenesis)
2. **Memory replay** (海马回放)
3. **Curriculum learning** (课程学习 — Elman 1993)
4. **Transfer learning** (迁移学习)
5. **Intrinsic motivation** (内在动机 — curiosity-driven)
6. **Multisensory integration** (多模态整合)

**对 helios 启示 — 6 大机制对位表**:
| Parisi 2019 6 机制 | helios owner + category |
|---|---|
| 1. Structural plasticity | 15 experience_writeback / structural plasticity (R86 4 层 store L4 神经补全) |
| 2. Memory replay | 06 memory / `replay_priority_policy` |
| 3. Curriculum learning | 09 thought_gating / `continuation_policy` |
| 4. Transfer learning | 10 directed_retrieval / `retrieval_planning_policy` |
| 5. Intrinsic motivation | 18 autonomy / `drive_integration_policy` |
| 6. Multisensory integration | 02 sensory_ingress (非 LPC，但 6 维 raw input owner) |

### 5. Einhauser & van Steenbergen 2018 "Pupil dilation as an index of effort"

**DOI**: 10.3758/s13423-018-1432-y (cited 917)
**核心论点**:
- pupil dilation = cognitive effort 指标
- 3 大 cognitive control domains：updating / switching / inhibition
- 高 task demand → 高 pupil dilation

**对 helios 启示**:
- **owner 04 norepinephrine system** = LC-NE system = pupillary control
- helios R70 neuromodulator→LLM 桥 (composition/bridges.py:1945-2400) 的
  **norepinephrine → "arousal" 文本投影** 跟 pupillometry 学术吻合
- owner 09 thought_gating 的 `signal_normalization_policy` 跟 "pupil
  dilation as effort" 学术对位

## 后续路线图 (R-PROTO-LEARN.11 ~ R-PROTO-LEARN.20)

基于 17 owner × 46 category 缺口 + 5 篇学术论文 + helios 现有架构，
**R-PROTO-LEARN.11+ 候选 10 个切片**（按优先级排序）：

### Tier 1: 神经机制对位 (R-PROTO-LEARN.11-15)

#### R-PROTO-LEARN.11 owner 06 memory 真学习 (P5 缺口)
- **LPC**: `memory_family_write_policy` / `replay_priority_policy` /
  `consolidation_policy` (3 category)
- **学术依据**: De Lange 2021 (replay-based) + Bhatt 2019 (LTP→DNA
  methylation dual-timescale) + Parisi 2019 (memory replay)
- **实施思路**:
  1. `replay_priority_policy`: LLM-based 优先级排序，按 affect intensity
     + prediction mismatch + autobiographical salience 加权
  2. `consolidation_policy`: 双时间尺度（fast LTP 模拟 R85 4 层 L4 短期
     store / slow DNA methylation 模拟 R85 4 层 L5 autobiographical 长期 store）
  3. `memory_family_write_policy`: 跟 owner 15 experience_writeback 的
     `consolidation_priority_policy` 协同
- **真 LLM 验证**: 18 长程对话观察 replay priority 排序

#### R-PROTO-LEARN.12 owner 09 thought_gating 真学习
- **LPC**: `gate_policy` / `continuation_policy` /
  `signal_normalization_policy` (3 category)
- **学术依据**: Einhauser 2018 (pupil dilation = effort) + Parisi 2019
  (curriculum learning)
- **实施思路**:
  1. `signal_normalization_policy`: norepinephrine → gate sensitivity
     学习（跟 Einhauser pupillometry 对位）
  2. `continuation_policy`: curriculum-aware（task 难度渐进）
  3. `gate_policy`: dopaminergic 信心门（已部分实现，扩展）
- **真 LLM 验证**: 12 任务难度渐进对话

#### R-PROTO-LEARN.13 owner 10 directed_retrieval 真学习
- **LPC**: `retrieval_planning_policy` / `tier_selection_policy` /
  `thought_window_shaping_policy` (3 category)
- **学术依据**: Parisi 2019 (transfer learning) + R85 4 层 store 路线
- **实施思路**:
  1. `tier_selection_policy`: L2 episodic / L3 semantic / L4
     autobiographical / L5 immutable — 跟 LLM context 协同
  2. `retrieval_planning_policy`: Panksepp SEEKING 启发的主动检索
  3. `thought_window_shaping_policy`: dopamine-modulated retrieval
- **真 LLM 验证**: 跨 tick 长程检索任务

#### R-PROTO-LEARN.14 owner 11 internal_thought 真学习
- **LPC**: `thought_generation_policy` / `sufficiency_policy` /
  `proposal_emission_policy` (3 category)
- **学术依据**: Kotseruba 2018 (metacognition 3 大机制 self-observation)
- **实施思路**:
  1. `thought_generation_policy`: 跟 R-PROTO-LEARN.7 P5-feel feeling
     输入协同（feeling → thought content）
  2. `sufficiency_policy`: R85 reconsolidation C+D 组合
  3. `proposal_emission_policy`: dopamine-modulated emission rate
- **真 LLM 验证**: 14 thought proposal 任务

#### R-PROTO-LEARN.15 owner 18 autonomy 真学习 (Phase 3 桥)
- **LPC**: `drive_integration_policy` / `continuity_carry_policy` /
  `proactive_externalization_policy` (3 category)
- **学术依据**: Parisi 2019 (intrinsic motivation / curiosity) +
  Kotseruba 2018 (self-regulation)
- **实施思路**:
  1. `drive_integration_policy`: 6 pressure + 1 threshold 真学习
     (跟 R-PROTO-LEARN.7 P5-feel hormone→feeling 闭环)
  2. `continuity_carry_policy`: 跨 tick 自我连续性（接 R85 phase 1
     cross-tick carry state）
  3. `proactive_externalization_policy`: self-regulation（**P6 入口**）
- **真 LLM 验证**: 8 自治驱动决策场景

### Tier 2: 跨 owner 协同 (R-PROTO-LEARN.16-18)

#### R-PROTO-LEARN.16 owner 14 identity_governance 真学习
- **LPC**: 4 category (`governance_evaluation_policy` /
  `pressure_interpretation_policy` / `supported_revision_policy` /
  `boundary_check_policy`)
- **学术依据**: Kotseruba 2018 (self-regulation) + R85 L18
  `forget_permission` 已有基础
- **实施思路**:
  1. 扩展 L18 forget_permission 现有 fail-closed 框架
  2. LLM-driven revision proposal evaluation
  3. 4 category 都接 R-PROTO-LEARN.15 自治压力信号
- **P6 入口** = supported_revision_policy

#### R-PROTO-LEARN.17 owner 15 experience_writeback 真学习
- **LPC**: 3 category (`continuity_classification_policy` /
  `consolidation_priority_policy` / `autobiographical_salience_policy`)
- **学术依据**: Bhatt 2019 (LTP→DNA methylation) + Parisi 2019
  (structural plasticity)
- **实施思路**:
  1. `autobiographical_salience_policy`: LLM-driven L5 immutable
     写入门
  2. `consolidation_priority_policy`: DNA methylation 模拟
  3. `continuity_classification_policy`: episodic / semantic /
     autobiographical 三家族分类

#### R-PROTO-LEARN.18 owner 17 evaluation 真学习
- **LPC**: 3 category (`fidelity_scoring_policy` /
  `gap_analysis_policy` / `long_range_diagnostic_policy`)
- **学术依据**: Kotseruba 2018 (self-analysis) — **P6 入口 2**
- **实施思路**:
  1. LLM-driven self-analysis（评估 P5 learning 是否成功）
  2. gap detection（P5/P6 目标 vs 实际）
  3. long_range diagnostic（跨 tick 长期稳定性）

### Tier 3: 末端 owner (R-PROTO-LEARN.19-20)

#### R-PROTO-LEARN.19 owner 13 planner_bridge + 12 action_externalization 真学习
- **LPC**: 6 category (3+3)
- **学术依据**: Kotseruba 2018 (action selection)

#### R-PROTO-LEARN.20 owner 07 workspace + 08 consciousness 真学习
- **LPC**: 6 category (3+3)
- **学术依据**: Kotseruba 2018 (consciousness / self-observation)
- **关键 insight**: consciousness 的 `commitment_policy` 是 P5→P6
  转化的最后桥

## 关键决策点（待小黑拍板）

### 决策 1: 路线图周期
- **A 选项**: 1 commit 1 slice，10 slice 1 周期（~2 周）
- **B 选项**: 1 commit 3 slice（同 owner 3 category 一起 ship，~3 周）
- **C 选项**: 1 commit ship 全部 10 slice（调研分支上 ship，~1 周）
- **小黑原话**："调研分支直接做最终目标全套" → C 倾向

### 决策 2: P5 vs P6 优先级
- **A 选项**: 先 P5 完整（15 owner × 46 category 全部 ship）→ 再 P6
- **B 选项**: P5 + P6 并行（owner 14 governance + 18 autonomy +
  17 evaluation 同步启动 P6 metacognition）
- **C 选项**: 先核心 5 owner（06/09/10/11/15）+ P6 入口（18/14/17），
  末端 5 owner 后续

### 决策 3: 学术 ground truth 优先级
- **A 选项**: 5 篇论文已够（Kotseruba/De Lange/Bhatt/Parisi/Einhauser）
- **B 选项**: 继续深挖 1-2 篇（如 Carhart-Harris REBUS / Yeshurun DMN
  review）
- **C 选项**: 加 1-2 篇主动 inference Friston 跟 owner 04 路线协同

### 决策 4: 不整合到 main
- **小黑原话**："该分支永远不会直接整合到 main"
- **实施**: 调研分支持续推 commit，**绝对不 merge** 到 main
- **后续**: 调研分支永远是 R&D sandbox，main 同步远端 main

## 范围限制

- 本文件是**深度调研**，**不立即开发**
- 等小黑拍板 4 个决策点后，**再启动 R-PROTO-LEARN.11**
- 调研分支保持 HEAD `291a429`（R-PROTO-LEARN.10）不动

## 调研报告参考

- `docs/requirements/research-p5-feel-10/result.md` (R-PROTO-LEARN.10 收官)
- `docs/requirements/research-p5-feel-9/result.md` (R-PROTO-LEARN.9 收官)
- `docs/requirements/research-p5-feel-fix-1/result.md` (R-PROTO-LEARN.8 收官)
- `docs/requirements/research-p5-feel/research_notes_v2_journals.md`
  (Panksepp 顶级期刊调研)
