# Requirement 97 - 去英文中心 / 中文 Appraisal Grounding（tasks）

> 配套：`requirement.md` + `design.md` + `probe_results.md`。
> 状态：草稿。主人拍板后开始 R97 实施。
> 依赖：R96（真实 embedding 接入，已收口）。

## 1. 切片依赖图

```
R96 真实 embedding ✓
  ↓
R97 中文 appraisal grounding
  ↓
R98 情感验收探针（待 R97 完成后才 ship）
  ↓
R99+ 双轨记忆（建在 R96 + R97 上）
```

## 2. 任务拆分

### Task 1 - 中文 prototype 集 + `appraisal.anchor_catalog` 新模块

**目标**：owner 拥有的多语 prototype catalog，引入中文 anchor；`appraisal` owner 仍拥有"哪一组是 threat / reward"的语义权威。

**子任务**：

1. **1.1** 创建 `helios_v2/src/helios_v2/appraisal/anchor_catalog.py`：
   - `AnchorSet` (frozen dataclass): `language: str`, `dimension: str`, `phrases: tuple[str, ...]`
   - `AnchorCatalog` (frozen dataclass): `sets: tuple[AnchorSet, ...]`
   - `AnchorCatalog.phrases_for(dimension: str) -> tuple[str, ...]`: 跨语种 union
   - `AnchorCatalog.sets_for(dimension: str) -> tuple[AnchorSet, ...]`: 按维度返回集合（保留语种信息）
   - `__post_init__` fail-fast：`sets` 非空；每个 `AnchorSet` 的 `phrases` 非空；`dimension in {"threat", "reward"}`
   - `ZH_THREAT_ANCHORS` / `ZH_REWARD_ANCHORS`（5 个中文 phrase / 类；手工 + PANAS-X 中文翻译）
   - `EN_THREAT_ANCHORS` / `EN_REWARD_ANCHORS`（**别名**指向 R40 旧 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES`，**不复制**）
   - `DEFAULT_ANCHOR_CATALOG`：中文 + 英文双锚点

2. **1.2** 在 `appraisal/__init__.py` 导出新符号。

**触发模块**：`helios_v2/src/helios_v2/appraisal/anchor_catalog.py` (new), `helios_v2/src/helios_v2/appraisal/__init__.py` (additive)。

**完成定义**：模块导入干净；`AnchorCatalog(sets=())` 抛 `ValueError`；`phrases_for("threat")` 跨语种 union 正确。

**验证**：`pytest helios_v2/tests/test_anchor_catalog.py -q` (Task 5.1)。

### Task 2 - `GroundedDimensionEstimator` 升级 prototype 字段

**目标**：把 `anchor_catalog` 字段加入 `GroundedDimensionEstimator`，保持 `threat_prototypes` / `reward_prototypes` 字段向后兼容。

**子任务**：

1. **2.1** 在 `appraisal.engine` 新增 import `from helios_v2.appraisal.anchor_catalog import DEFAULT_ANCHOR_CATALOG, AnchorCatalog`。
2. **2.2** 在 `GroundedDimensionEstimator` dataclass 新增字段 `anchor_catalog: AnchorCatalog = DEFAULT_ANCHOR_CATALOG`（在 `threat_prototypes` / `reward_prototypes` 之后）。
3. **2.3** 修改 `estimate_dimensions` 的 threat / reward 评分逻辑：
   ```python
   threat_prototypes_max = self.prototype_source.max_similarity_to(stimulus, self.threat_prototypes)
   catalog_threat_max = self.prototype_source.max_similarity_to(stimulus, self.anchor_catalog.phrases_for("threat"))
   # Take the max of the two, falling back to 0.0 only when both are None
   threat_fact = _max_of_two(threat_prototypes_max, catalog_threat_max)
   ```
4. **2.4** 添加 `_max_of_two` 私有 helper（接受两个 `float | None`，返回更大的非 None，或 0.0 当两者都 None）。
5. **2.5** 现有 `threat_gain` / `reward_gain` 字段保留；max-of-max 不改变 gain 系数。

**触发模块**：`helios_v2/src/helios_v2/appraisal/engine.py`。

**完成定义**：
- `GroundedDimensionEstimator(threat_prototypes=..., threat_gain=1.0, ...)` 的现有调用形态**字节级保持**（catalog 默认值是 `DEFAULT_ANCHOR_CATALOG`，旧测试不走 max-of-max 改造的旧路径——因为旧测试都走 `legacy_constant` 装配的 `FirstVersionDimensionEstimator`，不走 `GroundedDimensionEstimator`，所以 catalog 升级不会影响 1110 baseline）。
- 当显式设 `anchor_catalog=AnchorCatalog(sets=(zh_threat,))` 时，新行为生效。

**验证**：`pytest helios_v2/tests/test_rapid_salience_engine.py -q` (Task 5.2)。

### Task 3 - `EmbeddingPrototypeSimilaritySource` 多语化

**目标**：source 在收到 `_catalog` 注入时对多语 prototype 做 max-of-max；不注入时行为字节级与 R40 一致。

**子任务**：

1. **3.1** 在 `composition.bridges` 新增 import `from helios_v2.appraisal.anchor_catalog import AnchorCatalog`。
2. **3.2** 在 `EmbeddingPrototypeSimilaritySource` dataclass 新增字段 `_catalog: AnchorCatalog | None = None`。
3. **3.3** 修改 `max_similarity_to`：
   - 计算 `prototypes_max = max(cosine(query, p) for p in prototypes)`（保留 R40 旧行为）；
   - 若 `_catalog` 注入，计算 `catalog_max = max(cosine(query, p) for p in _catalog.phrases_for(<owner-determined-dimension>))`；
   - 返回 `max(prototypes_max, catalog_max)`。
4. **3.4** 新增 helper 方法 `_max_similarity_for_dimension(query_vector, dimension)`，避免在 `max_similarity_to` 中重复 cosine 计算。

**owner 边界问题与解决**：`max_similarity_to(stimulus, prototypes)` 不知道传入的 `prototypes` 是 threat 还是 reward（这是 owner 的语义）。R97 的 catalog 注入需要 source 知道 dimension。最简方案：

- 在 source 注入时**同时**传入 catalog 与 dimension 索引（`_catalog: AnchorCatalog, dimension: str`）；
- `max_similarity_to` 在拿到 `prototypes` 时，**对比** `prototypes` 与 `catalog.phrases_for(dimension)` 的元组；若相同（即 owner 传入的就是 catalog 抽取的 phrases），直接对所有 catalog phrases 做 max；否则按旧行为做 prototypes max + catalog max 取大。

**更简单的方案（采纳）**：source 始终做 `max(传入 prototypes_max, catalog.phrases_for(<owner-set-dim>)_max)`。owner 通过 `_catalog` 字段的 dimension 关联（source 持有一个 `_catalog_dimension: str` 字段）告诉 source 这是 threat 还是 reward 的 catalog。`max_similarity_to` 不需要知道传入 prototypes 的 dimension，因为它和 catalog 是独立的 max 输入。

最终设计：
```python
@dataclass
class EmbeddingPrototypeSimilaritySource(PrototypeSimilaritySource):
    embed_text: Callable[[str], tuple[float, ...]]
    _prototype_cache: dict[tuple[str, ...], tuple[tuple[float, ...], ...]] = field(default_factory=dict, repr=False)
    _catalog: AnchorCatalog | None = None
    _catalog_dimension: str | None = None  # "threat" or "reward"

    def max_similarity_to(self, stimulus, prototypes) -> float | None:
        text = stimulus.content.strip()
        if not text or not prototypes:
            return None
        query_vector = self.embed_text(text)
        prototypes_max = max(cosine_similarity(query_vector, v) for v in self._prototype_vectors(prototypes))
        if self._catalog is not None and self._catalog_dimension is not None:
            catalog_phrases = self._catalog.phrases_for(self._catalog_dimension)
            if catalog_phrases:
                catalog_max = max(cosine_similarity(query_vector, v) for v in self._prototype_vectors(catalog_phrases))
                return max(prototypes_max, catalog_max)
        return prototypes_max
```

**触发模块**：`helios_v2/src/helios_v2/composition/bridges.py`。

**完成定义**：
- 当 `_catalog` 与 `_catalog_dimension` 都不注入时，行为字节级与 R40 一致。
- 当两者都注入时，max-of-max 生效。

**验证**：`pytest helios_v2/tests/test_r97_chinese_grounding.py -q` (Task 5.2)。

### Task 4 - composition 装配默认注入中文 prototype

**目标**：`composition.runtime_assembly` 在 `default_signal_mode == "semantic"` 装配 `GroundedDimensionEstimator` 时，自动注入 `DEFAULT_ANCHOR_CATALOG`（通过 `anchor_catalog` 字段的默认值）以及 `_catalog` + `_catalog_dimension` 到 `EmbeddingPrototypeSimilaritySource`。

**子任务**：

1. **4.1** 修改 `composition.runtime_assembly` 的 `GroundedDimensionEstimator` 构造点：保留现有 5 个 source 参数 + 现有 `threat_prototypes` / `reward_prototypes` 字段显式赋值（让 R40 旧测试通过）；新增 `anchor_catalog=DEFAULT_ANCHOR_CATALOG` 字段。
2. **4.2** 修改 `EmbeddingPrototypeSimilaritySource` 构造点：新增 `_catalog=DEFAULT_ANCHOR_CATALOG`（**对 threat 维度**）。但 source 同时被用于 threat 和 reward，所以需要**两个 source 实例**：
   ```python
   threat_source = EmbeddingPrototypeSimilaritySource(
       embed_text=_embed_text,
       _catalog=DEFAULT_ANCHOR_CATALOG,
       _catalog_dimension="threat",
   )
   reward_source = EmbeddingPrototypeSimilaritySource(
       embed_text=_embed_text,
       _catalog=DEFAULT_ANCHOR_CATALOG,
       _catalog_dimension="reward",
   )
   ```
   然后 `GroundedDimensionEstimator` 接收两个 source，**不**只接收一个。
3. **4.3** 扩展 `GroundedDimensionEstimator` 协议：当前 `PrototypeSimilaritySource` 是单 source；R97 让 `GroundedDimensionEstimator` 接受 `threat_source: PrototypeSimilaritySource` + `reward_source: PrototypeSimilaritySource` 两个字段。现有 `prototype_source: PrototypeSimilaritySource` 字段保留（向后兼容旧测试），在 `estimate_dimensions` 中 threat 用 `threat_source`、reward 用 `reward_source`、当两者未显式注入时回退到 `prototype_source`。

**owner 边界**：catalog 是 owner 注入的 candidate 集合；source 不知道这是 threat 还是 reward（由 `_catalog_dimension` 字段显式标记，由 composition 注入）—— 这是 composition 注入维度的最小契约。

**触发模块**：`helios_v2/src/helios_v2/appraisal/engine.py`（`GroundedDimensionEstimator` 扩展 threat_source / reward_source 字段）+ `helios_v2/src/helios_v2/composition/bridges.py`（构造时实例化两个 source）+ `helios_v2/src/helios_v2/composition/runtime_assembly.py`（装配两个 source）。

**完成定义**：1110 baseline 全部保留；`default_signal_mode == "semantic"` 装配时中文输入有非零 threat/reward 评分。

**验证**：`pytest helios_v2/tests/test_runtime_composition.py -q` + `pytest helios_v2/tests/test_r97_chinese_grounding.py -q`。

### Task 5 - R97 测试

**目标**：证明 R97 的中文 grounding 闭合 B3 根因。

**子任务**：

1. **5.1** `helios_v2/tests/test_anchor_catalog.py` — 6 单元测试（`design.md` §5.4）：
   - `test_default_catalog_includes_zh_and_en`
   - `test_zh_threat_anchors_are_chinese_only`
   - `test_zh_anchors_distinct_from_en_anchors`
   - `test_anchor_catalog_frozen`
   - `test_phrases_for_returns_union`
   - `test_catalog_with_only_zh_works`

2. **5.2** `helios_v2/tests/test_r97_chinese_grounding.py` — 8 grounding 测试（`design.md` §5.5）：
   - `test_zh_threat_input_scores_high_threat_under_zh_anchors`
   - `test_zh_reward_input_scores_high_reward_under_zh_anchors`
   - `test_zh_neutral_input_scores_low_threat_and_reward`
   - `test_en_anchors_still_work_under_catalog`
   - `test_catalog_max_dominates_when_injected`
   - `test_catalog_fallback_when_no_zh_anchor_matches`
   - `test_estimator_default_catalog_works_without_injection`
   - `test_learned_catalog_can_replace_default`

3. **5.3** `helios_v2/tests/r97_b3_closure.py` — 3 B3 closure 测试（`design.md` §5.6）：
   - `test_b3_cortisol_separation_under_chinese_anchors`
   - `test_b3_recall_over_recency_preserved_for_chinese`
   - `test_b3_anchors_dont_break_english_anchors`
   - 每个测试输出 `B3ClosureReport` 到 `logs/r97_b3_closure/`，assertion 是 `b3_closed: bool == True`（中文 fixture 下）。

4. **5.4** `helios_v2/tests/test_no_adhoc_logging_guard.py` 与 `helios_v2/tests/test_composition_owner_boundary_guard.py`（无变化，必须通过）。

5. **5.5** **no-regression 扫描**：运行 `helios_v2/tests/ -q`，验证 1110 + R95-followup + R96-new + R97-new 全部绿；4 skipped 与 5 pre-existing wall-clock-profile + lt1 failures 保持现状。

**触发模块**：`helios_v2/tests/test_anchor_catalog.py` (new), `helios_v2/tests/test_r97_chinese_grounding.py` (new), `helios_v2/tests/r97_b3_closure.py` (new)。

**完成定义**：所有新测试通过；1110 baseline 全部保留；R56/R57 owner-boundary + R95-followup no-adhoc-logging guards 通过。

**验证**：`pytest helios_v2/tests/ -q` (full suite)。

### Task 6 - 真实 LLM emotion probe 集成

**目标**：`scripts/r96_b2_real_llm_probes/analyze.py` 加入 B3 判定，R97 自动级联到 R96 探针。

**子任务**：

1. **6.1** 在 `analyze.py` 的 `__main__` 中，加入 B3 metric 计算：
   - 中文负面 fixture（"愤怒"/"恐惧"/"悲伤"/"厌恶"等）的 threat 评分均值
   - 中文正面 fixture（"喜悦"/"感恩"/"爱"/"自豪"/"希望"/"敬畏"/"平静"等）的 reward 评分均值
   - 中文中性 fixture 的 threat / reward 评分均值
   - B3 verdict: 中文中"威胁 - 中性" ≥ 0.3 AND "奖励 - 中性" ≥ 0.3
2. **6.2** 在 `r96_emotion_analysis.json` 中加入 `b3_closure` 字段（`b3_closed: bool | None`, `b3_verdict_reason: str`）。
3. **6.3** 文档化 B3 判定逻辑（在 `analyze.py` docstring 中）。

**触发模块**：`helios_v2/scripts/r96_b2_real_llm_probes/analyze.py`。

**完成定义**：
- 离线（hash 路径）下 `b3_closed: None`（与 B2 一致：probe 没跑在真实 cloud 上）。
- 真实 cloud + R97 中文 anchors 下 `b3_closed: True`（如果 B3 metric 通过）。
- `analyze.py` 离线烟测 85 句跑通，输出 `b3_closed: None`。

**验证**：跑 `python helios_v2/scripts/r96_b2_real_llm_probes/run.py --offline && python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py`，看 `b3_closed: None` 正确输出。

### Task 7 - 文档同步

**目标**：把 R97 同步到所有 R96 同步过的文档（`index.md` / `ROADMAP.zh-CN.md` / `ARCHITECTURE_BOUNDARIES.md` / `BRAIN_ARCHITECTURE_COMPARISON.md` / `PROGRESS_FLOW.{zh-CN,en}.md` / `probe_results.md`）。

**子任务**：

1. **7.1** `docs/requirements/index.md`：新增 R97 行（紧跟 R96）。
2. **7.2** `docs/ROADMAP.zh-CN.md`：Status 头部记录 R97 拍板。
3. **7.3** `docs/ARCHITECTURE_BOUNDARIES.md`：Status 头部记录 R97；3.4 节加入 `appraisal.anchor_catalog` 模块的 row。
4. **7.4** `docs/BRAIN_ARCHITECTURE_COMPARISON.md`：Status 头部记录 R97；§5 加入 `gap_multilingual_prototype_grounding` 行。
5. **7.5** `docs/PROGRESS_FLOW.{zh-CN,en}.md`：Status 头部记录 R97。
6. **7.6** `docs/requirements/97-chinese-appraisal-grounding/probe_results.md`：R97 B3 closure 探针结果（中文 fixture 在 threat/reward cosine 上的方向性提升）。

**触发模块**：上述 5 个文档 + `probe_results.md`。

**完成定义**：所有 R96 同步过的文档都有 R97 的对应更新；R97 拍板记录 + 探针结果 + 边界规则。

**验证**：跑完 no-regression 后人工 review 每个文档的相关章节。

### Task 8 - 探针结果记录

**目标**：`docs/requirements/97-chinese-appraisal-grounding/probe_results.md` 记录 B3 闭合证据。

**子任务**：

1. **8.1** 创建 `probe_results.md` placeholder（同 R96 风格）。
2. **8.2** 在 R97 实施完成后填入 B3 closure 真实数据（中文 fixture 在 threat / reward 上的方向性提升）。
3. **8.3** 网络无 B3 闭合判定（`r97_b3_closure.py` 的 3 个测试结果）。
4. **8.4** 真实 LLM opt-in 探针结果（post-merge）。

**触发模块**：`docs/requirements/97-chinese-appraisal-grounding/probe_results.md`。

**完成定义**：B3 closure 证据完整记录。

## 3. 总体完成定义

- 7 个新文件 + 3 个修改文件
- 17 个新测试（6 catalog + 8 grounding + 3 B3 closure）
- 1110 baseline 全部保留
- R56/R57 owner-boundary + R95-followup no-adhoc-logging + R96 R96-followup guards 通过
- B3 closure（中文 fixture 方向性提升）通过

## 4. 风险与依赖

1. **依赖 R96**：R97 必须等 R96 收口才能开始（已完成 ✓）。
2. **中文 anchor 词表质量**：选词不合适会导致 B3 不闭合。**缓解**：在 `test_r97_chinese_grounding.py` 显式测试近义情绪的区分度。
3. **跨语言子空间对齐**：text-embedding-3-small 对中英文的子空间不对齐，max-of-max 可能偏向某一侧。**缓解**：先 ship 翻译锚点（成本最低），把"跨语种子空间对齐"留作 P5 评估子任务。
4. **P5 学习循环接口预留**：`AnchorCatalog` 是 frozen dataclass + `sets: tuple[AnchorSet, ...]`，未来学习循环可注入新 catalog 替换默认；本切片不实现学习循环。
