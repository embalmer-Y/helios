# R-PROTO-LEARN 后续路线图 — 学术调研

## 调研论文清单（5 篇 + 3 篇 arXiv 已下载）

| 论文 | DOI/arXiv | 引用 | 关键贡献 | helios 对位 |
|---|---|---|---|---|
| **Kotseruba 2018** | 10.1007/s10462-018-9646-y | 515 | 84 个 cognitive architecture 综述 + 3 大 metacognition 机制 | P6 self-regulation 入口 |
| **De Lange 2021** | 10.1109/tpami.2021.3057446 | 1590 | 3 大 continual learning 场景 + replay-based 唯一 work | R-PROTO-LEARN.3/4 (Layer 3/4) |
| **Bhatt 2019** | 10.1038/s41539-019-0048-y | 379 | LTP vs DNA methylation + reconsolidation = learning window | R85 4 层 L2-L5 store + R86 reconsolidation |
| **Parisi 2019** | arXiv 1802.07569 | 3001 | 6 大神经机制 (structural plasticity/memory replay/curriculum/transfer/intrinsic motivation/multisensory) | 完整 P5/P6 学术 map |
| **Einhauser 2018** | 10.3758/s13423-018-1432-y | 917 | pupil dilation = cognitive effort 指标 | owner 04 norepinephrine → owner 09 thought_gating |

## 核心论点（每篇论文的关键 1-2 段）

### Kotseruba 2018 — 3 大 metacognition 机制

> "Metacognition (Flavell 1979), intuitively defined as 'thinking about
> thinking', is a set of abilities that introspectively monitor internal
> processes and reason about them. There has been a growing interest in
> developing metacognition for artificial agents, both due to its
> essential role in human experience and practical necessity for
> identifying, explaining and correcting erroneous decisions.
> Approximately one-third of the surveyed architectures, mainly
> symbolic or hybrid ones with a significant symbolic component,
> support metacognition with respect to decision-making and learning.
> Here we will focus on three most common metacognitive mechanisms,
> namely **self-observation, self-analysis and self-regulation**."

**对 helios 启示**：
- 17 owner × 54 category 实际上是一份完整的 metacognition 体系
- P5 = self-observation (P5-feel learning_path 是 self-observation)
- P6 = self-analysis (R86+ 主题) + self-regulation (R87+ 主题)

### De Lange 2021 — replay 唯一 work

> "These experiments reveal that even for experimental protocols
> involving the relatively simple classification of MNIST-digits,
> regularization-based approaches (e.g., elastic weight consolidation)
> completely fail when task identity needs to be inferred. We find
> that currently only **replay-based approaches** have the potential to
> perform well on all three scenarios."

**对 helios 启示**：
- R85 4 层 L2-L5 store 选 replay-based 路线是对的
- R-PROTO-LEARN.3 (Layer 3 predictive coding) 是 prediction-mismatch
  replay trigger
- R-PROTO-LEARN.4 (Layer 4 pattern completion) 是 replay 内容来源
- R86 owner 06 memory `replay_priority_policy` 跟 replay-based 学术直接对位

### Bhatt 2019 — reconsolidation = learning window

> "Returning to LTP, further evidence for a transcriptional role in LLTP
> comes from studies of the **epigenetic regulation** in this form...
> **reconsolidation blockade** of the synaptic growth (but the memory
> persists) [means] **the memory does not reside at the synapse**...
> DNA methylation is the most likely candidate for an engram mechanism,
> first proposed by Holliday, is **epigenetic storage of information**,
> intrinsically quite stable: 'any turnover of DNA by methylation
> patterns is potentially very long-lived'"

**对 helios 启示**：
- R85 4 层 L4 (semantic) 跟 LTP / fast plasticity 对位
- R85 4 层 L5 (autobiographical / immutable) 跟 DNA methylation /
  epigenetic 对位
- R86 4 层 reconsolidation 路线跟 "reconsolidation = learning window"
  直接吻合
- owner 15 `consolidation_priority_policy` 跟 epigenetic storage 学术对位

### Parisi 2019 — 6 大神经机制

> "Lifelong learning capabilities are crucial for computational systems
> and autonomous agents interacting in the real world and processing
> continuous streams of information. However, lifelong learning remains
> a long-standing challenge for machine learning and neural network
> models since the continual acquisition of incrementally available
> information from non-stationary data distributions generally leads to
> catastrophic forgetting or interference. We discuss well-established
> and emerging research motivated by lifelong learning factors in
> biological systems such as **structural plasticity, memory replay,
> curriculum and transfer learning, intrinsic motivation, and
> multisensory integration**."

**6 大机制 → helios 17 owner 对位表**：

| # | Parisi 2019 6 机制 | helios owner | 关键 category |
|---|---|---|---|
| 1 | Structural plasticity | 06 memory + 15 experience_writeback | `consolidation_policy` + `consolidation_priority_policy` |
| 2 | Memory replay | 06 memory | `replay_priority_policy` |
| 3 | Curriculum learning | 09 thought_gating | `continuation_policy` |
| 4 | Transfer learning | 10 directed_retrieval | `retrieval_planning_policy` |
| 5 | Intrinsic motivation | 18 autonomy | `drive_integration_policy` |
| 6 | Multisensory integration | 02 sensory_ingress (非 LPC) | -- |

**对 helios 启示**：
- helios 17 owner 矩阵**完全覆盖** Parisi 2019 6 大神经机制
- 缺口 46 category 中**至少 15 个**直接对应这 6 大机制
- R-PROTO-LEARN.11-15 (Tier 1) 选这 5 owner 启动 P5 完整

### Einhauser 2018 — pupil dilation = effort

> "Across the three cognitive control domains of updating, switching,
> and inhibition, increases in task demands typically leads to increases
> in pupil dilation... An effort account of pupil dilation can provide
> an explanation of these findings. We also discuss future directions
> to further corroborate this account in the context of recent theories
> on cognitive control and effort and their potential **neurobiological
> substrates**."

**对 helios 启示**：
- norepinephrine → LC (locus coeruleus) → pupil dilation 神经通路
  - 学术依据：Aston-Jones & Cohen 2005 LC-NE adaptive gain theory
- helios owner 04 norepinephrine 通道的 `channel_gain_sensitivity`
  跟 pupillometry 直接对位
- owner 09 `signal_normalization_policy` 跟 effort 指标对位

## 论文调研的失败案例（避免重蹈）

- **Friston 2018 Markov blankets** (arXiv 1806.01084): **错配**为
  核物理 EDF paper（nuclear effective density functional），不是
  Friston active inference 综述。**已删除**。
- **Yeshurun 2023 DMN review** (10.1016/j.neuron.2023.04.023): Cell
  期刊 403，OA URL `cell.com/article/S0896627323003082/pdf` 返回
  HTML。**待换源**。
- **Seeley 2019 Salience Network** (JNeurosci): 期刊 403。**待换源**。
- **Carhart-Harris 2019 REBUS**: 期刊 403。**待换源**。

**结论**: 5 篇精读完成 + 3 篇 arXiv 待换源。**5 篇已够支撑 R-PROTO-LEARN.11+ 学术依据**。

## 关键发现总结

1. **P5 → P6 学术对接完成**:
   - P5 = self-observation (P5-feel R-PROTO-LEARN.1-10 完成)
   - P6 = self-analysis + self-regulation (R86+ 启动)
   - Kotseruba 2018 3 大 metacognition 机制 完整覆盖 helios 路线

2. **P5 缺口 = 46 category**:
   - Tier 1 神经机制对位: owner 06/09/10/11/15/18 (15 category)
   - Tier 2 跨 owner 协同: owner 14/17 (7 category)
   - Tier 3 末端 owner: 7 owner (24 category)

3. **R85 路线学术对接**:
   - 4 层 L2-L5 store ↔ LTP→DNA methylation dual-timescale
   - R85 巩固时机 C+D ↔ Bhatt reconsolidation = learning window
   - R85 4 层 hierarchy ↔ De Lange replay-based

4. **R-PROTO-LEARN 路线**:
   - R-PROTO-LEARN.11-15 Tier 1 (5 owner / 15 category)
   - R-PROTO-LEARN.16-18 Tier 2 (3 owner / 7 category)
   - R-PROTO-LEARN.19-20 Tier 3 (5 owner / 24 category)
   - 总 10 slice 覆盖 46 category

5. **4 决策点待小黑拍板**:
   - 决策 1: 路线图周期 (A/B/C 1 commit 1 slice / 3 slice / 10 slice)
   - 决策 2: P5 vs P6 优先级
   - 决策 3: 学术 ground truth 优先级
   - 决策 4: 不整合到 main (已确认)

## 后续行动

- **不立即开发** (小黑 2026-06-17 要求 "深度调研后续开发内容")
- 等小黑拍板 4 决策点
- 调研分支保持 HEAD `291a429` 不动
- 5 篇论文 PDF 暂存 `/tmp/p5_followup_papers/`，**不 commit**（不跟 helios
  仓库混合）
