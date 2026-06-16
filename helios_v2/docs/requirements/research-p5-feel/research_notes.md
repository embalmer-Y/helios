# Research Notes: P5-feel — 大脑"感受"机制学术调研

> 配套 requirement.md / design.md / task.md
> 范围：owner 05 feeling P5 真学习切片的神经科学 ground truth

## 1. 调研范围

为 P5-feel（owner 05 feeling 9 channel hormone → 7 dim feeling 映射的**真学习**）寻找：
- 神经科学 ground truth（大脑怎么做）
- 学术范式综合（怎么工程实现）
- 验证方法（怎么证明有效）

## 2. 核心论文（**3 篇已 download + 精读**）

### 2.1 Fermin, Yamawaki, Friston (2021) — **核心论文**

- **标题**："Insula Interoception, Active Inference and Feeling Representation"
- **期刊**：Frontiers in Neural Circuits (Opinion paper, 2021)
- **arXiv**：2112.12290
- **作者**：Alan S. R. Fermin (Hiroshima), Shigeto Yamawaki (Hiroshima), Karl Friston (UCL, **free-energy principle 创始人**)
- **PDF**：`/tmp/insula_active_inference.pdf` (1.4MB, 22 页)

**核心模型：IMAC = Insula Hierarchical Modular Adaptive Interoception Control**

#### 关键发现 1：三层岛叶 + 三并行回路

| 岛叶模块 | PFC 搭档 | 纹状体 | 学习阶段 | 含义 |
|---|---|---|---|---|
| **gINS** (granular insula, posterior) | SMA (supplementary motor area) | pStr (posterior striatum) | **habitual** | 已学会的快速 interoceptive 预测 |
| **dINS** (dysgranular insula, mid) | DLPFC (dorsolateral PFC) | dmStr (dorsomedial striatum) | **model-based** | 预测 interoceptive state 未来 |
| **aINS** (agranular insula, anterior) | VMPFC (ventromedial PFC) | vStr (ventral striatum) | **exploratory** | 全新 interoceptive-state mapping |

**学习时序**：
1. 早期学习 = aINS 探索 + dINS model-based
2. 行为稳定后 = gINS habitual
3. 新场景 = 重新激活 aINS 探索 → dINS model → gINS habitual

#### 关键发现 2：mesaception vs metaception 概念

- **1st order mesaception**（subcortical/brain stem）：
  - 先天基础情绪（hunger, fear, anger）
  - 存储未学习驱动的神经表征
  - 触发先天行为（consummatory, approach, aggression）

- **2nd order metaception**（insula cortex）：
  - 高级皮层表征 mesaception
  - 产生 conscious feelings
  - 把基础情绪转化为 conscious feeling

- **3rd order（PFC）**：
  - 反思 / introspection
  - 估计 meaning, causes, consequences

**精确对应 helios 6 层 emotion system + P5-feel**：

| 神经层 | helios 对应 |
|---|---|
| mesaception (1st) | L1 fallback（R40/R97/R98 26 条 hardcoded）|
| metaception (2nd) | **P5-feel 9→7 mapping**（**本切片核心**）|
| 3rd order (PFC) | owner 11 internal_thought 反思 |

#### 关键发现 3：4 大神经递质角色

| 神经递质 | 角色 | helios 对应 |
|---|---|---|
| **多巴胺（DA）** | **precision signal**（预测置信度）+ life-supporting | dopamine channel（已 ship，R36/R80）|
| **乙酰胆碱（ACh）** | **flexibility**（dINS/aINS 新映射）+ stability（gINS 已学）| acetylcholine channel |
| **谷氨酸（Glu）** | 兴奋（新映射）| excitation channel |
| **GABA** | 抑制（gINS 稳定化）| inhibition channel |

**4 大功能**：
1. **Parallel networks (insula-PFC-striatum)** 专门做 interoceptive policy hierarchical generation
2. **Dopamine** = precision signal + life-supporting
3. **Acetylcholine** = flexibility + stability
4. **Metaception / mesaception** 解耦 cortical vs subcortical 表征

#### 关键发现 4：helios 9 通道 hormone 1-to-1 精确对应

| helios channel | IMAC 角色 |
|---|---|
| dopamine | precision signal（helios R81 corroboration 已 ship）|
| acetylcholine | 灵活性（helios R36/R40 attention gating）|
| cortisol | 急性应激（learned prediction error）|
| serotonin | 长期稳态（allostasis set point）|
| oxytocin | social interoception |
| opioid_tone | pleasure / pain regulation |
| excitation | Glu（兴奋）|
| inhibition | GABA（抑制）|
| norepinephrine | alertness / stress（reticular activating system）|

### 2.2 Reddan, Chang, Kragel, Wager (2018) — embodied emotion 实证

- **标题**："Somatosensory and motor contributions to emotion representation"
- **arXiv**：2411.08973
- **作者**：Marianne Reddan (Einstein), Luke Chang (Dartmouth), Phil Kragel (Emory), Tor Wager (Dartmouth)
- **PDF**：`/tmp/somatomotor_emotion.pdf` (1.5MB)

**方法**：
- fMRI N=21 + 身体图谱（volunteers 标"哪里有感觉"）
- 112 张 IAPS/GAPED 高唤醒情绪图片
- 18 维 appraisal 量表
- Representational Similarity Analysis (RSA)

**关键发现**：
- **双侧 primary somatosensory cortex** + **motor cortex** + **insula** + **medial PFC** 网络
- 身体图谱在 fMRI 有可分神经表征
- **情绪不是纯认知** —— 有 sensorimotor cortical activation
- 跨样本（in-lab N=21 + online N=128）high fidelity

**精确对应 helios 7 维 feeling**：

| helios feeling dim | 神经对应区域 |
|---|---|
| **valence**（好坏）| insula + mPFC 整合 |
| **arousal**（兴奋度）| norepinephrine 系统 + 脑干网状结构 |
| **tension**（紧张）| somatosensory cortex（"胸口发紧"）|
| **pain**（痛苦）| anterior cingulate cortex (ACC) |
| **agency**（主动感）| motor cortex / SMA |
| **temporal**（时间感）| medial PFC |
| excitation / inhibition | Glu / GABA 神经递质对 |

### 2.3 Hinrichs, Albarracin, Bolis et al. (2025) — 几何 hyperscanning

- **标题**："Geometric Hyperscanning of Affect under Active Inference"
- **arXiv**：2506.08599
- **作者**：Nicolás Hinrichs (Max Planck), Mahault Albarracin (VERSES AI), Leonhard Schilbach (LMU)
- **PDF**：`/tmp/geometric_affect.pdf` (3.2MB)

**核心创新**：
- **Valence = self-model prediction error weighted by self-relevance**
  （感受 = "我预测错了多少" × "这对我多重要"）
- **Temporal aiming** = 跨时间的 affective appraisal
- **Coupled active inference** for dyadic interaction
- **Forman-Ricci curvature** = inter-brain 拓扑重配置指标
  （"突然情绪转折 / 重新建立连接" 都可以测度）

**对位 helios R-PROTO-LEARN.6**（社会共识层）：
- self-model prediction error = L3 预测编码
- identity-relevant surprise = L5 贝叶斯 emotion concept
- Forman-Ricci curvature = P4 网络通道的"情感转折"指标

## 3. 经典论文（已在 R-PROTO-LEARN research_notes.md 收录）

### 3.1 Seth (2013) "Interoceptive inference, emotion, and the embodied self"
- *Trends in Cognitive Sciences*
- 经典 interoceptive inference 框架
- "Feelings as controlled hallucinations"（感受 = 受控幻觉）

### 3.2 Barrett (2017) "The theory of constructed emotion"
- *Seminars in Speech and Language*
- Lisa Feldman Barrett 构造情绪理论
- 情绪 = 概念化（categorization），不是预成模块

### 3.3 Friston (2010) "The free-energy principle: a unified brain theory?"
- *Nature Reviews Neuroscience*
- 自由能 + 主动推理
- 整个大脑 = 预测机器

## 4. 5 大 ground truth 总结

| # | 神经科学真相 | helios P5-feel 启示 |
|---|---|---|
| **A** | 感受是**3 层**：mesaception (innate) → metaception (cortical) → PFC introspection | 保留 L1 hardcoded + 学 metaception + owner 11 反思 |
| **B** | 学习是 **DA precision + ACh flexibility 双驱** | 学习范式必须双信号，不是单纯 reward |
| **C** | **三学习阶段**：habitual / model-based / exploratory | 三态切换，不是单一学习率 |
| **D** | 学习是**先探索后固化** | lifelong 多阶段（不是一次性拟合）|
| **E** | 验证靠 **fMRI / 行为学学习曲线** | helios 跑 R83 长跑 + R88 漂移 + R89 图灵 |

## 5. helios P5-feel 落地的具体对位

### 5.1 9→7 维 mapping 1-to-1

```
9 hormone channels (input):
  dopamine  → DA precision
  acetylcholine  → ACh flexibility
  cortisol  → learned prediction error
  serotonin  → allostasis set point
  oxytocin  → social interoception
  opioid_tone  → pleasure / pain
  excitation  → Glu
  inhibition  → GABA
  norepinephrine  → alertness

7 feeling dim (output):
  valence  → insula + mPFC
  arousal  → NE + reticular
  tension  → somatosensory cortex
  pain  → ACC
  agency  → motor cortex / SMA
  temporal  → mPFC
  (其他 1 维)  → integration
```

### 5.2 学习范式（**3 态差异化**）

```python
# HABITUAL（gINS-equivalent）: 高 DA precision + 低 ACh flexibility
W_new = W + lr * outer(h, e) * dopamine_precision * 0.5

# MODEL_BASED（dINS-equivalent）: DA precision * ACh flexibility 全开
W_new = W + lr * outer(h, e) * dopamine_precision * ach_flexibility

# EXPLORATORY（aINS-equivalent）: ACh flexibility 主导，DA precision 弱
W_new = W + lr * outer(h, e) * ach_flexibility  # DA 不 gate
```

### 5.3 验证方法（学术+工程）

| 学术方法 | helios 工程方法 |
|---|---|
| fMRI 验证 | R88 漂移评估 |
| 行为学学习曲线 | R83 长跑 JSONL + 早期-晚期窗口对比 |
| 双人脑 hyperscanning | R89 图灵 harness |
| 神经电生理 | R-PROTO-LEARN.2 真 LLM appraisal |
| 神经递质调控实验 | helios 9 channel hormone 调节实验 |

## 6. 与 R-PROTO-LEARN 6 层的关系

| R-PROTO-LEARN 层 | 神经对应 | P5-feel 关系 |
|---|---|---|
| L1 fallback (R40/R97/R98) | mesaception (innate) | 保留 hardcoded |
| L1 interoception (.1) | DA + cortisol precision | 部分已 ship（heuristic bias）|
| L2 LLM appraisal (.2) | aINS exploratory | **P5-feel 消费作 ground truth** |
| L3 predictive coding (.3) | prediction error | 不直接耦合 |
| L4 pattern completion (.4) | dINS model-based | 不直接耦合（后续可加）|
| L5 Bayesian concept (.5) | 3rd order introspection | 部分已 ship |
| **owner 05 feeling (R36/R43)** | **metaception (2nd order)** | **P5-feel 核心场** |

## 7. 不属本调研（明确排除）

- 1st order mesaception（L1 fallback hardcoded）—— 不学
- 3rd order PFC introspection（owner 11 internal_thought）—— 后续切片
- 社会 affective（Hinrichs 2025 hyperscanning）—— R-PROTO-LEARN.6 远期
- 双人脑 hyperscanning 真实 fMRI 验证—— 不可做
- 神经递质调控实验真实 fMRI 验证—— 不可做

## 8. 落地提案（5 项 1 commit）

**新增切片**：P5-feel（research branch 直接 ship）

| # | 切片 | 算法 | 神经对应 |
|---|---|---|---|
| 1 | 探索阶段 | R-PROTO-LEARN.2 LLM appraisal 作 ground truth | aINS exploratory |
| 2 | 固化阶段 | 连续 N tick mapping 不变 → 写入 config | gINS habitual |
| 3 | 精度信号（DA） | mapping 残差 ↔ dopamine 调 confidence | R81 precision signal |
| 4 | 灵活性信号（ACh） | novelty ↔ acetylcholine 决定是否学新 mapping | Fermin 2021 ACh 角色 |
| 5 | 三态切换 | aINS / dINS / gINS = R88 漂移收敛触发 | Fermin 2021 IMAC 三回路 |

**5 项 = 1 commit = 1 验证**（按小黑 2026-06-16 ~19:50 拍板）

## 9. 与既有 R-PROTO-LEARN 6 层架构的边界

- **输入边界**：消费 R-PROTO-LEARN.2 LLM appraisal（7 维）+ 9 通道 hormone + novelty + DA + ACh
- **输出边界**：7 维 feeling（替换 R36/R43 hardcoded W/bias → 学习的 W/bias）
- **不耦合**：R-PROTO-LEARN.3/.4/.5 不直接读 P5-feel W（通过 owner 05 state 间接读）

## 10. 实施时间线

- **T1 (60 min)**：写 `feeling/learning_path.py` 主体
- **T2 (30 min)**：owner 05 集成
- **T3 (45 min)**：写 30+ 测试
- **T4 (5 min)**：整库测试
- **T5 (30 min)**：真 LLM smoke 改造
- **T6 (5 min)**：真 LLM smoke 跑
- **T7 (30 min)**：暴露 bug 修
- **T8 (5 min)**：commit + push
- **总计**：~3.5 小时（不切分）

## 11. 决策点（已拍板）

- **分支**：research/R-PROTO-LEARN-appraisal-multi-mechanism
- **不切分**：5 项 1 commit ship
- **验证**：真 LLM smoke + 整库测试 + 行为验收
- **失败处理**：暴露 bug 同 commit 修；根本性不可行 → 报告小黑
