# Task: R-PROTO-LEARN — 6 个子切片 Outline

> **配套**：`requirement.md` + `design.md` + `research_notes.md`。
> **状态**：调研阶段（仅 outline，不写代码）。
> **作者**：小白，2026-06-16 06:30-（调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` from main `15b4650`）

---

## 1. 调研任务清单（不写代码）

| Task | 内容 | 状态 | 估时 |
|---|---|---|---|
| T1 | 创建调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` from main | ✅ 完成 | 1 min |
| T2 | 验证 main baseline 干净（1117 passed, 3 skipped, 0 failed） | ✅ 完成 | 3 min |
| T3 | 写 `requirement.md` | ✅ 完成 | 30 min |
| T4 | 写 `design.md` | ✅ 完成 | 45 min |
| T5 | 写 `task.md`（本文档） | ✅ 完成 | 30 min |
| T6 | 写 `research_notes.md`（11 篇论文 + 5 理论依据） | 📝 进行中 | 1h |
| T7 | 跟 R97/R98/R96/R85 现有切片对接方案确认 | 📝 待续 | 1h |
| T8 | MVP 3 周切片 outline（.6 + .5 + .1） | 📝 待续 | 1h |
| T9 | 完整 6-8 周切片 outline（.1-6 全部） | 📝 待续 | 1h |
| T10 | 风险评估 + owner 边界检查 | 📝 待续 | 1h |
| T11 | 提交调研 commit（小黑拍板前不 push） | 📝 待续 | 5 min |
| T12 | 小黑拍板（进入 MVP 实施 / 全套实施 / 调整范围） | ⏳ 等小黑 | — |

---

## 2. 6 个子切片 Outline

### 2.1 R-PROTO-LEARN.1 (Layer 1 内感受 / Active Inference)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 04 神经调质（hormone）+ owner 11 LLM（mapping） |
| **目标** | 17-dim hormone 当前值影响 appraisal 5 维（Layer 1 → Layer 3/4 输入） |
| **依赖** | R36（appraisal → hormone）+ R81（hormone predict corroboration）|
| **不依赖** | LLM 实时预测（Layer 2）|
| **改动** | `appraisal/engine.py` `GroundedDimensionEstimator` 入口加 `current_hormone_state` 参数；`map_hormone_to_appraisal` 函数 |
| **不改动** | 17-dim hormone 状态；R36 appraisal → hormone 方向 |
| **MVP 简化** | 不接 LLM，用简单数学：hormone mean → baseline appraisal adjustment |
| **风险** | 中（LLM 评估 hormone → appraisal 映射的训练数据需要构造） |
| **估时** | 1 周 |
| **验收** | hormone state 影响 appraisal 5 维；B3 metric ≥ +0.10 (fake LLM) |

### 2.2 R-PROTO-LEARN.2 (Layer 2 预测 / Predictive Coding)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 11 LLM |
| **目标** | LLM 预测 + 比对实际 → surprise score（输入 Layer 1） |
| **依赖** | R81 hormone-predict corroboration（升级路径） |
| **不依赖** | Layer 1（surprise 计算可独立） |
| **改动** | `appraisal/engine.py` 加 `predict_and_compare`；`PredictiveCodingSurprise` 数据契约 |
| **不改动** | R81 next-tick 模式（保留作为 Layer 5 反馈） |
| **MVP 简化** | 不用 LLM，用 cosine(recent_input_embedding, current_input_embedding) |
| **风险** | 中（每次 tick 多 1 次 LLM 调用） |
| **估时** | 1-2 周 |
| **验收** | surprise score 影响 cortisol 上升；cortisol 正负分离 ≥ +0.10 (fake LLM) |

### 2.3 R-PROTO-LEARN.3 (Layer 3 记忆 / Pattern Completion)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 06 memory |
| **目标** | R85 memory store 加 `recall_similar(n, outcome_class)` 检索方法 |
| **依赖** | R85 + R10 + R96 既有 |
| **不依赖** | 其他 Layer |
| **改动** | `memory/store.py` 加 `recall_similar` 方法；不新增 owner/路径 |
| **不改动** | R99-R104 既有切片（R99-R104 在 6 层架构里属于 Layer 3 主体） |
| **MVP 简化** | 直接用 R10 directed_retrieval + outcome_class 过滤 |
| **风险** | 低（R85 + R10 + R96 成熟） |
| **估时** | 3-5 天（主要是"对接文档"） |
| **验收** | R85.recall_similar(input, n=5, outcome_class="threat") 返回 5 条相似 threat memory |

### 2.4 R-PROTO-LEARN.4 (Layer 4 构造 / Constructed Emotion)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 11 LLM |
| **目标** | LLM 实时构造 emotion concept（输入 Layer 5） |
| **依赖** | Layer 1 + Layer 2 + Layer 3 |
| **改动** | owner 11 LLM 加 `construct_emotion_concept` 输出；`EmotionConcept` 数据契约 |
| **不改动** | R98 post-LLM hormone（边界：R98 调制 hormone，R-PROTO-LEARN.4 构造 concept） |
| **MVP 简化** | 不接 LLM 实时构造，用固定 ~10 个常见 emotion concept 字典 |
| **风险** | 高（每次 tick 多 1 次 LLM 调用；concept 质量难评估） |
| **估时** | 2 周 |
| **验收** | emotion concept 跟 R88/R89 评估指标方向一致；CAREBench-style evaluation |

### 2.5 R-PROTO-LEARN.5 (Layer 5 学习 / Bayesian Update)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 06 memory + owner 03 appraisal |
| **目标** | 每次 emotion concept 构造后，Bayesian update prior |
| **依赖** | Layer 4 + R100 importance |
| **改动** | `appraisal/engine.py` 加 `EmotionPriorState` 字段；`bayesian_update_emotion_prior` 函数；跟 R100 双写机制对接 |
| **不改动** | appraisal 5 维输出接口；R36 appraisal → hormone 路径 |
| **MVP 简化** | 简单计数更新（每次 observation 后 P(concept) += learning_rate * 1）|
| **风险** | 中（learning rate 调参；跟 R100 双写机制对接） |
| **估时** | 1 周 |
| **验收** | 10 次观察后 emotion concept 概率分布稳定；B3 metric ≥ +0.05 (fake LLM) |

### 2.6 R-PROTO-LEARN.6 (Layer 6 Fallback / EmoGist)

| 字段 | 内容 |
|---|---|
| **Owner** | owner 03 appraisal |
| **目标** | R97/R98 21 条 phrase 升级为 description；context-dependent retrieval |
| **依赖** | R97 + R98 既有 anchors |
| **不依赖** | 其他 Layer（fallback 是独立兜底） |
| **改动** | `appraisal/anchor_catalog.py` `AnchorSet` 加 `description` 字段；`estimate_dimensions` 加 description cosine 路径 |
| **不改动** | R97/R98 现有 anchor 字段（保留为 description 字段来源） |
| **MVP 简化** | 直接手工写 description（不调 LLM） |
| **风险** | 极低（R97/R98 已有路径保留） |
| **估时** | 3-5 天 |
| **验收** | 中文输入"胸口闷得慌"命中 description（即使没命中 phrase）；1174 baseline 测试全 pass |

---

## 3. MVP 3 周切片依赖图

```
Week 1: R-PROTO-LEARN.6 (fallback)        ─┐
                                            ├─→ 都可独立交付
Week 2: R-PROTO-LEARN.5 (Bayesian)        ─┤   不阻塞其他切片
                                            │
Week 3: R-PROTO-LEARN.1 (interoception)   ─┘
```

**MVP 切片选 3 个低风险层**：
- .6 极低（纯字段升级）
- .5 中（升级 R100 现有路径）
- .1 中（加 hormone → appraisal 映射）

**为什么这 3 个先做**：
- 6 极低：先打地基，验证 R97/R98 兼容性
- 5 中：复用 R100 现有 importance 路径
- 1 中：复用 17-dim hormone 现有状态

**为什么 .2 + .4 留后**：
- .2 改 owner 11 LLM 核心逻辑，风险高
- .4 涉及 emotion concept 新概念，要 LLM 实时构造

---

## 4. 完整 6-8 周切片依赖图

```
Week 1: .6 fallback
  ↓
Week 2: .5 Bayesian
  ↓
Week 3: .1 interoception
  ↓
Week 4-5: .2 predictive coding (LLM predict + compare)
  ↓
Week 6-7: .4 constructed emotion (LLM concept)
  ↓
Week 8: 6 层融合 + 整体验收

并行（不依赖 .1-6）：
- .3 memory recall_similar (跟 R99-R104 对接，3-5 天)
```

**关键路径**: .6 → .5 → .1 → .2 → .4 → 融合
**并行支路**: .3（独立 3-5 天）

---

## 5. 风险评估

### 5.1 每切片风险

| 切片 | 风险 | 影响 | 缓解 |
|---|---|---|---|
| .1 interoception | 中 | LLM 映射训练数据 | MVP 用数学简化 |
| .2 predictive coding | 中 | LLM 调用成本 | MVP 用 embedding 距离 |
| .3 memory recall | 低 | 既有 R85/R10 成熟 | 直接复用 |
| .4 constructed emotion | 高 | LLM 实时构造 + concept 质量 | MVP 用固定字典 |
| .5 Bayesian | 中 | learning rate 调参 | MVP 用简单计数更新 |
| .6 fallback | 极低 | 纯字段升级 | 直接手工 |

### 5.2 跨切片风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 6 层融合后 latency 增量 | 中 | MVP 限定 < 200ms/tick |
| 跟 R98 post-LLM hormone 边界冲突 | 中 | 明确划分：R98 调制 hormone，R-PROTO-LEARN.4 构造 concept |
| 跟 R100 双写机制对接 | 中 | 复用 R100 schema |
| 6 层数据流无环 | 低 | 已验证（见 design.md §1.2） |
| 跟 R99-R104 切片不重复 | 低 | 已验证（见 design.md §3.5） |

### 5.3 owner 边界

| owner | 当前在 appraisal 的角色 | R-PROTO-LEARN 新增 | 是否冲突 |
|---|---|---|---|
| owner 03 appraisal | 5 维输出 | Layer 6 fallback + Layer 5 Bayesian 反馈 | 不冲突（追加） |
| owner 04 神经调质 | 17 hormone | Layer 1 interoception（hormone → appraisal 方向） | **边界确认**：R36 appraisal → hormone 方向保留；新增反向 |
| owner 06 memory | R85 既有 | Layer 3 recall_similar + Layer 5 Bayesian update | 不冲突（追加） |
| owner 11 LLM | R98 既有 | Layer 2 prediction + Layer 4 concept construction | **边界确认**：R98 调制 hormone（hormone Δ）；R-PROTO-LEARN.4 构造 concept（不直接输出 hormone） |
| owner 14 governance | 既有 | 无新增 | 不参与 |

---

## 6. 验收矩阵

| 验收项 | MVP 3 周 | 完整 6-8 周 |
|---|---|---|
| 1174 baseline 测试全 pass | ✅ 必须 | ✅ 必须 |
| 60 新测试（.1/.5/.6） | ✅ 必须 | ✅ |
| 120+ 新测试（.1-6 全部） | — | ✅ 必须 |
| 真实云端 B3 cortisol 分离 ≥ +0.10 | ✅ 必须 | ✅ |
| 真实云端 B2 cortisol 分离 ≥ +0.05 | ✅ 必须 | ✅ |
| 6 层架构跑通 | Layer 6+5+1 跑通 | 6 层全跑通 |
| appraisal latency 增量 < 200ms/tick | ✅ 必须 | ✅ 必须 |
| R-PROTO-LEARN.2 predictive coding 跑通 | ❌ 不在 MVP | ✅ 必须 |
| R-PROTO-LEARN.4 constructed emotion 跑通 | ❌ 不在 MVP | ✅ 必须 |
| 6 层融合无环 + 边界清晰 | ✅ 必须 | ✅ 必须 |

---

## 7. 调研结束条件

| 条件 | 状态 |
|---|---|
| 4 个调研文档（requirement + design + task + research_notes）全部完成 | 📝 进行中 |
| 跟 R97/R98/R96/R85/R99-R104 既有切片对接方案明确 | 📝 待续 |
| 风险评估完成 | ✅ 完成（本文档 §5） |
| MVP 3 周切片 outline 明确 | ✅ 完成（本文档 §3） |
| 完整 6-8 周切片 outline 明确 | ✅ 完成（本文档 §4） |
| 验收矩阵明确 | ✅ 完成（本文档 §6） |
| 小黑拍板（进入实施阶段） | ⏳ 等小黑 |

---

_Generated by 小白 on 2026-06-16 06:30-。仅调研，不写代码。_
