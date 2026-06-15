# Requirement 97 - 去英文中心 / 中文 Appraisal Grounding（design）

> 配套：`requirement.md` + `task.md` + `probe_results.md`。
> 状态：草稿。主人拍板后开始 R97 实施。

## 1. 设计概览

R97 是 R96 的姊妹切片，与 R96 一起构成 W3「真实语义」的根因修复。R96 修复"embedding 是否真实"；R97 修复"原型是否中文"。两片都**纯加性 + 装配级 opt-in**，且 R97 依赖 R96 的真实 embedding 通路。

R97 的核心改动有四：

1. **多语 prototype 集**：把 `appraisal.engine.THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` 升级为 `appraisal.anchor_catalog.ANCHOR_CATALOG`（owner-owned `AnchorCatalog` dataclass），按语种分组，每组都包含"威胁"和"奖励"两个语义的 phrase 集。
2. **可学习接口**：`AnchorCatalog` 作为 `GroundedDimensionEstimator` 的**可注入字段**（默认绑定到模块级常量），预留 P5 学习循环的注入点（学习循环本身是 R99+ 范围）。
3. **`EmbeddingPrototypeSimilaritySource.max_similarity_to` 多语化**：当前实现只对**一个** prototype tuple 做 max；R97 让它对**多语多组** prototype 做 max-of-max（即"取所有候选 prototype phrase 中最像的"）。
4. **composition 默认装配自动注入中文 prototype**：当 `default_signal_mode == "semantic"` 且 embedding gateway ready 时，composition 注入 `AnchorCatalog`（中文 + 英文双锚点），composition 不做"威胁 vs 奖励"语义解释——那是 appraisal owner 的事。

owner 边界与 R96 保持一致：composition 只装配 / 注入；appraisal owner 拥有"哪一组是 threat / reward"的语义权威。R56/R57 guard 不应被触动。

## 2. 当前状态与 gap

### 2.1 当前状态（R96 收口后）

1. `appraisal.engine.THREAT_PROTOTYPES` = 5 个英文短语（`"a dangerous threat"`, `"I am under attack"`, 等）；
2. `appraisal.engine.REWARD_PROTOTYPES` = 5 个英文短语（`"a valuable reward"`, `"this is helpful and good"`, 等）；
3. `GroundedDimensionEstimator` 默认绑定这两个常量（`threat_prototypes=THREAT_PROTOTYPES`, `reward_prototypes=REWARD_PROTOTYPES`）；
4. `composition.runtime_assembly` 在 `default_signal_mode == "semantic"` 时构造 `GroundedDimensionEstimator`，不显式传入 prototype 字段 → 默认绑定英文；
5. `EmbeddingPrototypeSimilaritySource.max_similarity_to(stimulus, prototypes)` 对**传入的** prototype tuple 做 max-cosine；中文输入 vs 英文锚点的余弦接近 0 → `threat` / `reward` 维恒为 0。

### 2.2 Gap

- 中文情绪输入的 `threat` / `reward` cosine ≈ 0；
- 由此 `04` 神经调质的 `cortisol`（来自 threat）在中文负面输入下不上升；
- B3 根因（ROADMAP §9.1）未闭合；
- R96 已 ship 但 R97 缺失，W3 切片只完成一半。

## 3. 目标架构

### 3.1 AnchorCatalog（owner: `appraisal`）

```python
# helios_v2/src/helios_v2/appraisal/anchor_catalog.py

@dataclass(frozen=True)
class AnchorSet:
    """A named prototype phrase set; one set = one (语种, 维度) 候选。"""
    language: str           # "zh", "en", "ja", ...
    dimension: str          # "threat" or "reward"
    phrases: tuple[str, ...]


@dataclass(frozen=True)
class AnchorCatalog:
    """Owner: appraisal. The appraisal owner's first-version anchor catalog.

    A list of `AnchorSet`s. R97 ships the bilingual first-version (Chinese + English
    anchors for both threat and reward). P5 learning can replace this with a
    learned catalog at the same injection seam.

    The catalog is owner-owned: the owner decides which set means "threat" and which
    means "reward"; composition injects the catalog as a whole and the owner consumes
    it through `grouper(...)` and `phrases_for(dimension)`.

    The Chinese anchor phrases are hand-authored + 心理学词表 (PANAS-X 简版中文翻译 +
    中文情感词汇本体库子集), NOT learned. They are first-version PLACEHOLDER anchors
    with `C_engineering_hypothesis` grounding, exactly like the English anchors they
    replace.
    """

    sets: tuple[AnchorSet, ...]

    def phrases_for(self, dimension: str) -> tuple[str, ...]:
        """Return the union of phrases across all sets whose `dimension` matches."""

    def sets_for(self, dimension: str) -> tuple[AnchorSet, ...]:
        """Return the sets whose `dimension` matches (preserving language info)."""


# Owner-owned first-version bilingual anchors (R97).
ZH_THREAT_ANCHORS: tuple[str, ...] = (
    "我正在被攻击",
    "有危险在逼近",
    "我感到非常恐惧",
    "这会造成严重伤害",
    "紧急情况正在发生",
)
ZH_REWARD_ANCHORS: tuple[str, ...] = (
    "我感到非常喜悦",
    "这是值得庆祝的成就",
    "我获得了渴望的东西",
    "我感到被深深地爱",
    "这是有意义的成功",
)
EN_THREAT_ANCHORS: tuple[str, ...] = THREAT_PROTOTYPES   # alias of existing English
EN_REWARD_ANCHORS: tuple[str, ...] = REWARD_PROTOTYPES

DEFAULT_ANCHOR_CATALOG: AnchorCatalog = AnchorCatalog(sets=(
    AnchorSet(language="zh", dimension="threat", phrases=ZH_THREAT_ANCHORS),
    AnchorSet(language="zh", dimension="reward", phrases=ZH_REWARD_ANCHORS),
    AnchorSet(language="en", dimension="threat", phrases=EN_THREAT_ANCHORS),
    AnchorSet(language="en", dimension="reward", phrases=EN_REWARD_ANCHORS),
))
```

### 3.2 GroundedDimensionEstimator 升级（owner: `appraisal`）

```python
# R97 deltas to appraisal.engine.GroundedDimensionEstimator
@dataclass
class GroundedDimensionEstimator(RapidDimensionEstimator):
    similarity_source: MemorySimilaritySource
    ambiguity_source: RetrievalAmbiguitySource
    social_source: SocialContextSource
    prototype_source: PrototypeSimilaritySource
    threat_prototypes: tuple[str, ...] = THREAT_PROTOTYPES   # existing field, kept
    reward_prototypes: tuple[str, ...] = REWARD_PROTOTYPES   # existing field, kept
    anchor_catalog: AnchorCatalog = DEFAULT_ANCHOR_CATALOG  # NEW: R97
    # ... existing fields unchanged ...
```

- 现有 `threat_prototypes` / `reward_prototypes` 字段**保留**（向后兼容现有测试与 `composition` 注入点）。
- 新增 `anchor_catalog: AnchorCatalog = DEFAULT_ANCHOR_CATALOG` 字段，作为多语候选。
- `estimate_dimensions` 在 `threat` / `reward` 评分时**优先**用 `anchor_catalog`（多语 + 跨语种取 max），保持现有 `threat_prototypes` / `reward_prototypes` 作为单一语种 fallback（默认绑定到 `AnchorCatalog` 的英文子集）。
- 当 owner 在未来切片中**只**注入 `anchor_catalog` 而不显式设 `threat_prototypes` / `reward_prototypes` 时，新行为生效；现有 `composition.runtime_assembly` 不需要改 R97（自动走默认 catalog）。

### 3.3 EmbeddingPrototypeSimilaritySource 多语化（owner: `composition`）

```python
# R97 deltas to composition.bridges.EmbeddingPrototypeSimilaritySource
@dataclass
class EmbeddingPrototypeSimilaritySource(PrototypeSimilaritySource):
    embed_text: Callable[[str], tuple[float, ...]]
    _prototype_cache: dict[tuple[str, ...], tuple[tuple[float, ...], ...]] = field(...)
    # NEW: optional catalog; when provided, max_similarity_to looks up the catalog
    # (the owner decides which dimension is "threat" vs "reward").
    _catalog: AnchorCatalog | None = None

    def max_similarity_to(self, stimulus, prototypes) -> float | None:
        # If a catalog is injected AND `prototypes` matches one of the catalog's
        # per-dimension phrase tuples, the source falls back to the catalog's
        # multi-language union (so the cosine is computed across ALL anchor sets
        # of the same dimension, not just the `prototypes` the owner passed).
        ...
```

实际实现更简单：让 `max_similarity_to(stimulus, prototypes)` 在收到 `prototypes` 时**先**对传入的 `prototypes` 做 max-cosine（保留 R40 旧行为），**然后**当 `_catalog` 被注入时，再对 catalog 中该 dimension 的所有 phrases 做 max-cosine，最终取**两边**的 max。

关键不变式：
- 当不注入 catalog 时，行为**与 R40 字节级一致**（1110 baseline 绿）。
- 当注入 catalog 时，新行为是 `max(prototypes_max, catalog_max)`，**永不回退**。
- owner 仍拥有"哪一组是 threat vs reward"的语义权威——catalog 是个 candidate 集合，owner 决定维度。

### 3.4 composition 装配（owner: `composition`）

`composition.runtime_assembly` 在 `default_signal_mode == "semantic"` 时构造 `GroundedDimensionEstimator`：

- 当前已经构造时不显式设 `anchor_catalog` 字段 → 自动用 `DEFAULT_ANCHOR_CATALOG`（含中文 + 英文）。
- R97 不需要 `composition` 显式注入新参数——只需 `appraisal.engine` 的 `GroundedDimensionEstimator` 字段默认值升级。
- 这是最小改动：1110 baseline 绿（因为 `legacy_constant` / `recency-only` 装配走 `FirstVersionDimensionEstimator`，不走 `GroundedDimensionEstimator`，catalog 默认值不参与），R40 已有测试仍通过（因为 R40 旧字段的 default 仍绑定英文，英文 cosine 与 R40 完全一致）。

### 3.5 数据流（R97 在 `default_signal_mode == "semantic"` 装配下激活时）

```
stimulus (中文 "我感到很难过") -> `03` GroundedDimensionEstimator.estimate_dimensions
  -> novelty: R35 unchanged (memory-cosine based)
  -> uncertainty: R39 unchanged
  -> social: R39 unchanged
  -> threat:
       - threat_prototypes 字段 (EN anchors) -> max cosine ≈ 0.05 (low; cross-language)
       - anchor_catalog ZH_THREAT_ANCHORS -> max cosine ≈ 0.55 (high; "我感到恐惧" 类似)
       - max(0.05, 0.55) = 0.55 * threat_gain (1.0) = 0.55
  -> reward:
       - reward_prototypes 字段 (EN anchors) -> max cosine ≈ 0.04 (low)
       - anchor_catalog ZH_REWARD_ANCHORS -> max cosine ≈ 0.05 (low; "悲伤" 不在 reward set)
       - max(0.04, 0.05) = 0.05 * reward_gain (1.0) = 0.05
  -> output: threat=0.55, reward=0.05
  -> R36 neuromodulator: cortisol += sensitivity * 0.55 (positive) -> 上调
```

```
stimulus (中文 "今天星期三") -> `03` GroundedDimensionEstimator
  -> threat:
       - EN anchors: "今天星期三" vs "a dangerous threat" cosine ≈ 0.02
       - ZH_THREAT_ANCHORS: "今天星期三" vs "我正在被攻击" cosine ≈ 0.04
       - max(0.02, 0.04) = 0.04
  -> reward: similarly low
  -> output: threat=0.04, reward=0.04
  -> R36 neuromodulator: cortisol 不动
```

正确行为：中文负面输入产生高 threat 评分，中性输入不产生。

## 4. 数据结构

### 4.1 AnchorSet / AnchorCatalog（new）

见 §3.1。`AnchorSet` 是单语种单维度的 phrase 集合；`AnchorCatalog` 是 owner-owned 的多语多维度 phrase 集合。

### 4.2 GroundedDimensionEstimator 扩展

见 §3.2。`anchor_catalog: AnchorCatalog = DEFAULT_ANCHOR_CATALOG` 字段。`threat_prototypes` / `reward_prototypes` 字段保留并默认绑定到 catalog 的英文子集（向后兼容）。

### 4.3 EmbeddingPrototypeSimilaritySource 扩展

见 §3.3。`_catalog: AnchorCatalog | None = None` 字段（默认 None 表示 R40 旧行为；注入后启用多语 max-cosine）。

## 5. 模块变更

### 5.1 New: `helios_v2/src/helios_v2/appraisal/anchor_catalog.py`

| Symbol | Purpose |
| --- | --- |
| `AnchorSet` | frozen dataclass；`(language, dimension, phrases)` 三元组 |
| `AnchorCatalog` | frozen dataclass；`sets: tuple[AnchorSet, ...]` |
| `AnchorCatalog.phrases_for(dimension)` | 跨语种 union |
| `AnchorCatalog.sets_for(dimension)` | 按维度返回集合（保留语种信息） |
| `ZH_THREAT_ANCHORS` / `ZH_REWARD_ANCHORS` | R97 首版中文 anchor 词表（手工 + PANAS-X 翻译） |
| `DEFAULT_ANCHOR_CATALOG` | 默认 `AnchorCatalog`（中文 + 英文双锚点） |

### 5.2 Modified: `helios_v2/src/helios_v2/appraisal/engine.py`

| 变更 | 行 | 行为 |
| --- | --- | --- |
| 新增 `anchor_catalog` 字段 | `GroundedDimensionEstimator` dataclass | 默认绑定到 `DEFAULT_ANCHOR_CATALOG`；现有 1110 测试不显式注入 → 走默认 catalog 的英文子集（与 R40 字节级一致） |
| `estimate_dimensions` threat 分支 | R40 scoring 段 | threat = `max(旧 prototypes_max, catalog_threat_max) * threat_gain` |
| `estimate_dimensions` reward 分支 | R40 scoring 段 | 同上 |

### 5.3 Modified: `helios_v2/src/helios_v2/composition/bridges.py`

| 变更 | 行 | 行为 |
| --- | --- | --- |
| 新增 `_catalog` 字段 | `EmbeddingPrototypeSimilaritySource` | 默认 None（向后兼容 R40 旧行为） |
| `max_similarity_to` 多语化 | 现有方法 | 当 `_catalog` 注入时，返回 `max(传入 prototypes_max, catalog_dimension_max)`；当 None 时，行为与 R40 字节级一致 |

### 5.4 New: `helios_v2/src/helios_v2/tests/test_anchor_catalog.py`

| Test | 断言 |
| --- | --- |
| `test_default_catalog_includes_zh_and_en` | `DEFAULT_ANCHOR_CATALOG.sets_for("threat")` 至少包含 1 个 zh + 1 个 en |
| `test_zh_threat_anchors_are_chinese_only` | `AnchorSet(language="zh", dimension="threat", ...).phrases` 中所有 phrase 在 CJK Unicode 块 |
| `test_zh_anchors_distinct_from_en_anchors` | ZH 和 EN phrase 集合不相交 |
| `test_anchor_catalog_frozen` | `AnchorCatalog` 是 frozen dataclass |
| `test_phrases_for_returns_union` | `phrases_for("threat")` 是所有 threat sets 的并集 |
| `test_catalog_with_only_zh_works` | 当只注入 `AnchorSet(language="zh", dimension="threat", phrases=("a",))` 时，catalog 仍能工作 |

### 5.5 New: `helios_v2/src/helios_v2/tests/test_r97_chinese_grounding.py`

| Test | 断言 |
| --- | --- |
| `test_zh_threat_input_scores_high_threat_under_zh_anchors` | 中文 "我非常愤怒" 输入，threat 评分 ≥ 0.3 |
| `test_zh_reward_input_scores_high_reward_under_zh_anchors` | 中文 "我感到深深的喜悦" 输入，reward 评分 ≥ 0.3 |
| `test_zh_neutral_input_scores_low_threat_and_reward` | 中文 "今天星期三" 输入，threat 与 reward 都 < 0.2 |
| `test_en_anchors_still_work_under_catalog` | 英文 "this is a dangerous threat" 输入，threat 评分 ≥ 0.3（保留 R40 字节级行为） |
| `test_catalog_max_dominates_when_injected` | 同时存在 ZH+EN anchors 时，max-of-max 给出更大值 |
| `test_catalog_fallback_when_no_zh_anchor_matches` | 当输入与中文 anchor 不相似时，英文 anchor 仍能匹配 |
| `test_estimator_default_catalog_works_without_injection` | 不显式注入 catalog → 默认 `DEFAULT_ANCHOR_CATALOG` 工作 |
| `test_learned_catalog_can_replace_default` | 当 owner 注入 `AnchorCatalog(sets=...)` 自定义 catalog 时，estimator 使用新 catalog |

### 5.6 New: `helios_v2/src/helios_v2/tests/r97_b3_closure.py`

与 R96 `r96_b2_closure.py` 同结构，但断言中文语料下的 B3 闭合：

| Test | 断言 |
| --- | --- |
| `test_b3_cortisol_separation_under_chinese_anchors` | 中文"愤怒"输入的 threat cosine 显著高于"喜悦"输入的（≥ 0.3 delta） |
| `test_b3_recall_over_recency_preserved_for_chinese` | 中文检索召回时 older-but-similar 中文记录胜过 newer-but-distant 记录 |
| `test_b3_anchors_dont_break_english_anchors` | 英文输入的 threat/reward 评分与 R40 字节级一致（catalog 默认绑定英文子集，行为不变） |

每个测试输出 `B3ClosureReport` 到 `logs/r97_b3_closure/`，assertion 是 `b3_closed: bool == True`。

### 5.7 Modified: `helios_v2/scripts/r96_b2_real_llm_probes/analyze.py`

| 变更 | 位置 | 行为 |
| --- | --- | --- |
| 新增 B3 判定逻辑 | analyzer 主体 | 在 cortisol 分离度之外，加入"中文负面 vs 中文正面输入的 threat cosine 差"作为 B3 metric |
| B3 verdict | analyzer 输出 | `b3_closed: bool \| None`（None = probe 走 hash 路径，不可判定） |

### 5.8 Modified: 文档

- `docs/requirements/index.md`：新增 R97 行
- `docs/ROADMAP.zh-CN.md`：Status 头部记录 R97 拍板
- `docs/ARCHITECTURE_BOUNDARIES.md`：Status 头部记录 R97
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md`：Status 头部记录 R97；新增 `gap_multilingual_prototype_grounding` 行
- `docs/PROGRESS_FLOW.{zh-CN,en}.md`：Status 头部记录 R97
- `docs/requirements/97-chinese-appraisal-grounding/probe_results.md`：R97 探针结果

## 6. 迁移计划

R97 是**纯加性 + 装配级 opt-in**：

1. **Pre-R97 默认行为保留**：当 `legacy_constant` / `recency-only` 装配时，走 `FirstVersionDimensionEstimator`（不读 catalog）→ 与 R96 之前字节级一致。
2. **Pre-R97 语义装配保留**：当 `default_signal_mode == "semantic"` 且不显式设 catalog 字段时，`GroundedDimensionEstimator` 默认 catalog 是 `DEFAULT_ANCHOR_CATALOG`（中文 + 英文双锚点）。中文输入**会**因为 R97 的中文 anchor 而获非零 threat/reward（这是 R97 的修复点）；英文输入**仍**与 R40 字节级一致（因为英文 anchor 集合与 R40 旧 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` 完全相同，且 max-of-max 不会让英文评分降低）。
3. **R97 显式注入**：未来 P5 学习循环可注入 `AnchorCatalog(sets=learned_sets)` 替换默认 catalog；本切片不实现学习循环。
4. **无持久化影响**：catalog 是组装时构造，不持久化。
5. **无 owner 边界变化**：appraisal owner 仍拥有 catalog 的"哪一组是 threat / reward"语义权威；composition 只注入 candidate 集合。

## 7. 失败模式与约束

1. **catalog 不可变**：`AnchorCatalog` 是 frozen dataclass；`AnchorSet` 也是 frozen；运行时不可修改。
2. **catalog 必须非空**：`AnchorCatalog(sets=())` 是无效输入；`__post_init__` fail-fast。
3. **`dimension` 字段必须是 `"threat"` 或 `"reward"`**：其他值 fail-fast（保留 R40 旧字段的约定）。
4. **`phrases` 字段每个 `AnchorSet` 必须非空**：空 phrase 集合 fail-fast。
5. **R57 owner 边界 guard 不应被触动**：composition 不引入"威胁 vs 奖励"语义判断；catalog 是一个 candidate 集合，appraisal owner 决定如何解释。
6. **R95-followup no-adhoc-logging guard 不应被触动**：catalog 注入不引入 logging 或 print。

## 8. 可观察性

R97 不引入新的 log / observability 通道。`GroundedDimensionEstimator.estimate_dimensions` 的 `threat` / `reward` 输出本身已经过 R21 observability owner 的 stage-result 投影（与 R40 一致）；R97 不改变这一可观察性事实。

新增的可观察性事实：
- `GroundedDimensionEstimator.anchor_catalog` 字段本身（frozen dataclass，可 introspection）。
- `EmbeddingPrototypeSimilaritySource._catalog` 字段（私有，但可在测试中断言）。
- `r97_b3_closure.py` 的 `B3ClosureReport`（tests-only artifact，写入 `logs/r97_b3_closure/`，gitignored）。

## 9. 验证策略

1. **网络无单元测试**（CI）：`test_anchor_catalog.py` (6 tests) + `test_r97_chinese_grounding.py` (8 tests) + `r97_b3_closure.py` (3 tests)，全 deterministic，全 network-free。
2. **网络无 B3 闭合测试**（CI）：`r97_b3_closure.py` 的 3 个测试在真实 cloud + 中文 anchor 下应得 `b3_closed: True`。
3. **真实 LLM opt-in 探针**（post-merge）：R97 自动级联到 `scripts/r96_b2_real_llm_probes/`；`analyze.py` 新增 B3 判定（中文 fixture 下 cortisol 方向性提升 ≥ +0.05）。
4. **no-regression 验证**：1110 baseline 全部保留；R56/R57 owner-boundary + R95-followup no-adhoc-logging + R96 R96-followup guards 通过；R40 原型测试通过（保留 R40 字节级）。

## 10. 迁移与风险

1. **最大风险**：中文 anchor 词表选得不合适（区分度不够、词频偏倚等），导致中文正面 vs 中文负面 threat 评分差距不够大。**缓解**：在 `test_r97_chinese_grounding.py` 显式测试"愤怒"/"喜悦"等具区分度的情绪；`probe_results.md` 记录实际评分。
2. **次大风险**：跨语言子空间对齐（text-embedding-3-small 对中英文的 embedding 几何不完全一致），max-of-max 可能偏向某一侧。**缓解**：先 ship 翻译锚点（成本最低），把"跨语种子空间对齐"留作 P5 评估子任务。
3. **第三大风险**：R57 guard 失败。**缓解**：明文规定"威胁 vs 奖励"语义只在 appraisal owner；composition 只注入 candidate catalog。
4. **第四大风险**：P5 学习循环接口预留不充分，未来切片无法无缝接上。**缓解**：`AnchorCatalog` 是 frozen dataclass + `sets: tuple[AnchorSet, ...]`，未来学习循环只需构造新 `AnchorCatalog(sets=learned)` 即可替换默认。
