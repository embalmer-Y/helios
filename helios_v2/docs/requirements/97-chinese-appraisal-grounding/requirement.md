# Requirement 97 - 去英文中心 / 中文 Appraisal Grounding（B3 根因闭合）

> 配套：`design.md` + `task.md` + `probe_results.md`。
> ROADMAP §9.1 B3 根因；§10 W3 #2。
> 依赖：R96（真实 embedding 接入）。
> 状态：草稿（开发计划阶段，2026-06-15）。主人拍板后开始 R97 实施。

## 1. 问题陈述（实证）

**R40 threat/reward 原型是英文**：当前 `helios_v2.appraisal.engine` 的 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` 是英文短语（`"a dangerous threat"`, `"this is helpful and good"` 等），作为 `GroundedDimensionEstimator` 的 prototype 锚点。在 R96 之后真实 embedding 接入使得 `EmbeddingPrototypeSimilaritySource` 能够做真实余弦计算，但**英文锚点 vs 中文输入的余弦接近 0**（不同语言子空间）—— 这是 ROADMAP §9.1 列出的 B3 根因：

- 中文情绪输入（"我感到很难过，世界很灰暗"）的 `threat` / `reward` 余弦近似 0；
- 因此 `03` 的 `threat` / `reward` 维对中文输入恒为 0；
- 因此 `04` 神经调质更新（`R36` appraisal-derived dynamics）的 `cortisol`（来自 threat）在中文负面输入下不上升；
- 因此 `cortisol` 正负情绪分离度（`analyze_emotion_test.py` 的 headline B3 metric）依然接近 0。

**R97 是 B3 的 root-cause 修复**，与 R96 一起构成 W3「真实语义」切片的两半。R96 解决 embedding 是否真实，R97 解决原型是否中文。

## 2. 范围

### 2.1 In scope

1. **中文 appraisal 原型集**：为 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` 引入中文短语集合，使中文输入有非零余弦。
2. **多语原型并行**：保留英文锚点作为 fallback；中文 + 英文集合**并行**进入 max-cosine 比较，取两集合各自的 max，再取大者。
3. **学习式原型（首版占位）**：原型集作为**可学习参数**（frozen dataclass + 可注入字段），预留 P5 系数学习的接口；首版仍是手工 + 心理学词表，**不**在此切片实现学习循环。
4. **owner 边界保护**：`03` appraisal owner 仍拥有"原型集是 threat/reward 定义"的语义权威；composition 只做翻译/注入，不做语义判断。
5. **owner 边界回归测试**：R56/R57 guard 不应被触动。

### 2.2 Out of scope（延后）

- **真实标注语料的弱监督聚类**（ROADMAP §8 item 6 选项 C）：需要外部数据；本切片只 ship 翻译锚点 + 心理学词表手工 anchor（ROADMAP §8 item 6 选项 A+B 混合的首版）。
- **P5 系数学习循环**：原型的可学习接口预留；学习循环本身是 R99+ 双轨记忆的一部分。
- **`11` LLM 二阶段重 appraisal**（ROADMAP §8 提到的"slow LLM re-appraisal"切片）：本切片不做。
- **BGE-M3 vs text-embedding-3-small 的中文效果对比**：是 P5 评估的子任务，不是 R97 的范围。

## 3. 退出信号（可证伪）

- R97 之后的 `cortisol` 正负情绪分离（`analyze_emotion_test.py` 的 headline metric）从 -0.0180（hash 路径）/ -0.0095（pre-R96 基线）方向性提升到 ≥ +0.05（中文负面输入下 cortisol 上升）。
- 在真实 cloud embedding + 中文原型的组装下：
  - 中文负面情绪文本（"愤怒"/"恐惧"/"悲伤"/"厌恶"/"羞耻"/"内疚"/"孤独"等）的 `threat` cosine > 0.3；
  - 中文正面情绪文本（"喜悦"/"感恩"/"爱"/"自豪"/"希望"/"敬畏"/"平静"等）的 `reward` cosine > 0.3；
  - 中性 / 工具型文本（"今天星期三"/"会议九点开始"等）的 `threat` 和 `reward` cosine 都在低区间（< 0.2）。
- 1110 baseline 全部保留（中文原型只在 `default_signal_mode="semantic"` 装配下生效；legacy_constant / recency-only 装配保持原常量原型 + 原常量 threat/reward 评分）。
- R56/R57 owner 边界 + R95-followup no-adhoc-logging guard 通过。

## 4. 切片轮廓（与 ROADMAP §10 W3 #2 一致）

R97 = **去英文中心 / 可学习的 appraisal grounding**。具体切片：

1. **多语 prototype 集**：把 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` 升级为 `THREAT_PROTOTYPES_MULTILINGUAL` / `REWARD_PROTOTYPES_MULTILINGUAL`（中文 + 英文并列），由 `EmbeddingPrototypeSimilaritySource.max_similarity_to` 跨语种取 max。
2. **可学习接口**：原型集作为 `GroundedDimensionEstimator` 的**可注入字段**（默认绑定到模块级常量），预留 P5 学习循环的注入点。
3. **中文词表选词**：手工 + 心理学词表（PANAS-X 简版中文翻译 + 中文情感词汇本体库子集），约 5-10 个中文 phrase / 类。
4. **owner 边界**：原型集的"中文 vs 英文"或"威胁 vs 奖励"语义仍归 `03` owner；composition 注入的是**多语候选**而非"威胁定义"。
5. **回归保护**：`GroundedDimensionEstimator` 的现有 1110 测试保持原行为（默认 prototype 集仍包含英文锚点 → 中文输入的低 threat/reward 是**已知预期**）；新增测试只覆盖"中文原型在 R97 注入后的 `GroundedDimensionEstimator` 上产出正确方向"。
6. **probe 集成**：把 R97 的中文原型集接入 `scripts/r96_b2_real_llm_probes/run.py` 的 emotion 装配（自动级联），使得 B2 探针自动也跑 R97；新增 B3 metric 在 `analyze.py` 的判定逻辑中。

## 5. 风险

1. **中文短语的余弦重叠**：joy 与 gratitude、fear 与 anxiety 等近义情绪在中文 embedding 上可能高度重叠，导致 threat/reward 评分区分度不足。**缓解**：选择具区分度的 anchor（"威胁"用"被攻击"/"危险逼近"等具体动词；"奖励"用"渴望"/"成就"等具体名词），并在 task.md 中显式测试近义情绪的区分度。
2. **跨语言子空间对齐**：text-embedding-3-small 对中文与英文的子空间不对齐，英文 + 中文锚点的 max-cosine 取大可能偏向更"顺"的那侧。**缓解**：先 ship 翻译锚点（成本最低），把"跨语种子空间对齐"留作 P5 评估子任务。
3. **R97 改动触发 owner 边界 guard**：把原型集从模块级常量升级为 dataclass 字段，若不小心把"威胁"或"奖励"语义塞进 composition（而非 appraisal owner），R57 guard 会失败。**缓解**：明确分工——composition 注入**多语候选**；appraisal owner 解释"哪一组是 threat"。

## 6. 任务拆分（task.md 详细）

完整子任务见 `task.md`。概要：
- Task 1: 中文 prototype 集设计 + `appraisal/anchor_catalog.py` 新模块（多语 + 可学习接口）
- Task 2: `GroundedDimensionEstimator` 升级 prototype 字段为可注入
- Task 3: `EmbeddingPrototypeSimilaritySource.max_similarity_to` 支持多语
- Task 4: composition 装配默认注入中文 prototype
- Task 5: B3 探针（中文 fixture 语料 + cosine 阈值断言）
- Task 6: 真实 LLM emotion probe 集成（自动级联到 R96 探针）
- Task 7: 文档同步（index.md / ROADMAP / PROGRESS_FLOW / BRAIN_ARCHITECTURE_COMPARISON）
- Task 8: no-regression 扫描 + R56/R57 guard

## 7. R97 vs R96 边界

| 维度 | R96（已收口） | R97（本切片） |
| --- | --- | --- |
| 根因 | 16-dim 哈希无语义 | 英文原型无中文语义 |
| 修复点 | composition 路由真实 cloud embedding | appraisal owner 拥有中文 prototype 集 |
| 触发条件 | `HELIOS_EMBEDDING_API_KEY` 存在 | `default_signal_mode == "semantic"` 装配自动激活 |
| 退出信号 | B2 network-free closure 测试 3/3 | B3 中文 fixture 在 `cortisol` 方向性提升 ≥ +0.05 |
| 探针位置 | `scripts/r96_b2_real_llm_probes/` | 复用 R96 探针，扩 `analyze.py` 加 B3 判定 |

R97 不重新实现 R96；它**用** R96 的真实 embedding 通路。
